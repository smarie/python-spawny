import multiprocessing as mp
import os
from importlib import import_module
from logging import Logger

import sys
from types import MethodType
from typing import Optional, Union, Any, List, Dict, Tuple

import logging


def init_mp_context():
    """
    multiprocessing toolbox setup
    :return:
    """
    mp.set_start_method('spawn')


# 'protocol' constants
OK_FLAG = True
ERR_FLAG = False
EXIT_CMD = 0
ATTR_OR_METHOD_CMD = 1
METHOD_CMD = 2
ATTR_CMD = 3


# default logger
_default_logger = logging.getLogger('pyoad')
ch = logging.StreamHandler(sys.stdout)
_default_logger.addHandler(ch)
# _default_logger.setLevel(logging.DEBUG)

# TODO maybe it is possible to actually send the initial object to the daemon. Not sure why it would be interesting..


class InstanceDefinition(object):
    """
    Represents the definition of an object instance to create.
    """

    def __init__(self, module_name: Optional[str], clazz_name: str, *args, **kwargs):
        """
        Creates a definition to instantiate an object of class `clazz_name` in module `module_name`, with constructor
        arguments *args and **kwargs. Submodules are supported, simply add them in `module_name` with the dot notation,
        such as 'os.path'. To create instances of build-in types such as 'int', set module_name to '' or None.

        :param module_name:
        :param clazz_name:
        :param args:
        :param kwargs:
        """
        self.module_name = module_name
        self.clazz_name = clazz_name
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return ('' if self.module_name is None else self.module_name) + '.' + self.clazz_name + '(' + str(self.args) \
               + ';' + str(self.kwargs) + ')'

    def get_type(self):
        """
        Utility method to return the class of objects corresponding to this definition
        :return:
        """
        # find the class, optionally from an imported module
        if self.module_name is not None and self.module_name != '':
            m = import_module(self.module_name)
            clazz = getattr(m, self.clazz_name)
        else:
            clazz = globals()[self.clazz_name]
        return clazz

    def instantiate(self):
        """
        Utility method to instantiate an object corresponding to this definition
        :return:
        """
        # find the class
        clazz = self.get_type()

        # instantiate
        return clazz(*self.args, **self.kwargs)


def replace_all_dundermethods_with_getattr(ignore, from_cls, to_cls_or_inst, is_class: bool,
                                           logger: Logger = _default_logger):
    """
    For all methods of from_cls replace/add a method on to_cls_or_inst that relies on __getattr__ to be retrieved.
    If is_class is false, to_cls_or_inst is an instance and only the new methods (not already on the class) will be
    replaced

    :param ignore:
    :param from_cls:
    :param to_cls_or_inst:
    :param is_class:
    :return:
    """
    def make_proxy(name):
        def proxy(self, *args):
            return self.__getattr__(name)
        return proxy

    to_replace = [name for name in dir(from_cls) if name.startswith("__") and name not in ignore]
    if is_class:
        logger.debug('Replacing methods ' + str(to_replace) + ' on class ' + to_cls_or_inst.__name__
                     + ' by explicit calls to __getattr__')
    else:
        to_replace = [name for name in to_replace if not hasattr(type(to_cls_or_inst), name)]
        logger.debug('Replacing methods ' + str(to_replace) + ' on instance ' + repr(to_cls_or_inst)
                     + ' by explicit calls to __getattr__')

    for name in to_replace:
        if is_class:
            # that means <name> is not in the ignore list, and not in the explicitly implemented methods (dct)
            # so for those ones, replace the class' method by a proxy redirecting explicitly to getattr
            # logger.debug('Replacing method ' + name + ' on class ' + to_cls_or_inst.__name__)
            setattr(to_cls_or_inst, name, property(make_proxy(name)))
        else:
            # logger.debug('Replacing method ' + name + ' on instance ' + repr(to_cls_or_inst))
            setattr(to_cls_or_inst, name, MethodType(make_proxy(name), to_cls_or_inst))


class ProxifyDunderMeta(type):
    def __init__(cls, name, bases, dct):
        type.__init__(cls, name, bases, dct)
        to_ignore = set("__%s__" % n for n in cls.__ignore__.split())
        to_ignore.update(set(dct.keys()))
        replace_all_dundermethods_with_getattr(to_ignore, cls, cls, is_class=True)
        # add everything from dict class so that at least
        replace_all_dundermethods_with_getattr(to_ignore, dict, cls, is_class=True)


class ObjectDaemonProxy(metaclass=ProxifyDunderMeta):
    """
    A proxy that spawns a separate process and delegates the methods to it.

    For the trick about redirecting all dunder methods to getattr, see
    https://stackoverflow.com/questions/9057669/how-can-i-intercept-calls-to-pythons-magic-methods-in-new-style-classes
    """

    __ignore__ = "class mro new init setattr getattr getattribute dict del dir doc name qualname module"

    def __init__(self, obj_instance_or_definition: Union[Any, InstanceDefinition], python_exe: str = None,
                 logger: Logger = _default_logger):
        """
        Creates a daemon running the provided object instance, and inits this Proxy to be able to delegate the calls to
        the daemon. Users may either provide the object instance, or a definition of instance to create. In that case
        the instance will be created in the daemon.

        :param obj_instance_or_definition: the object instance to use in the daemon, or the definition that the daemon
        should follow to create the object instance
        :param python_exe: the optional python executable to use to launch the daemon. By default the same executable
        than this process will be used.
        :param logger: an optional custom logger. By default a logger that prints to stdout will be used.
        """
        self.started = False
        self.logger = logger or _default_logger

        # --proxify all dunder methods from the instance type
        # unfortunately this does not help much since for new-style classes, special methods are only looked up on the
        # class not the instance. That's why we try to register as much special methods as possible in ProxifyDunderMeta
        instance_type = obj_instance_or_definition.get_type() \
            if isinstance(obj_instance_or_definition, InstanceDefinition) else type(obj_instance_or_definition)
        replace_all_dundermethods_with_getattr(set("__%s__" % n for n in ObjectDaemonProxy.__ignore__.split()),
                                               instance_type, self, is_class=False)

        # --set executable (actually there is no way to ensure that this is atomic with mp.Process(), too bad !
        if python_exe is not None:
            mp.set_executable(python_exe)

        # --init the multiprocess communication queue/pipe
        self.parent_conn, child_conn = mp.Pipe()
        # self.logger.info('Object proxy created an interprocess communication channel')

        # --spawn an independent process
        self.logger.info('Object proxy spawning Child process for object daemon')
        self.p = mp.Process(target=daemon, args=(child_conn, obj_instance_or_definition),
                            name=python_exe or 'python' + '-' + str(obj_instance_or_definition))
        self.p.start()
        self.started = True

    def is_started(self):
        return self.started

    def __repr__(self):
        if not self.is_started():
            return 'ObjectDaemonProxy<not started>'
        else:
            return 'ObjectDaemonProxy<' + self.remote_call_using_pipe(METHOD_CMD, '__repr__') + '>'

    def __getattr__(self, name):
        """
        Dynamic proxy

        :param name:
        :return:
        """
        if not self.is_started():
            return super(object, self).__getattr__(name)
        else:
            attr_typ = self.remote_call_using_pipe(ATTR_OR_METHOD_CMD, name)

            if attr_typ == ATTR_CMD:
                return self.remote_call_using_pipe(ATTR_CMD, name)

            elif attr_typ == METHOD_CMD:
                # generate a remote method proxy with that name
                def remote_method_proxy(*args, **kwargs):
                    return self.remote_call_using_pipe(METHOD_CMD, name, *args, **kwargs)
                return remote_method_proxy

    def remote_call_using_pipe(self, cmd_type: int, meth_or_attr_name: str = None, *args, **kwargs):
        """
        Calls a remote method

        :param cmd_type: command type (EXIT_CMD, METHOD_CMD, ATTR_CMD)
        :param meth_or_attr_name:
        :param args:
        :param kwargs:
        :return:
        """
        if not self.is_started():
            raise Exception('Cannot perform remote calls - daemon is not started')

        if cmd_type == METHOD_CMD:
            log_str = 'execute method'
        elif cmd_type == ATTR_CMD:
            log_str = 'access attribute'
        elif cmd_type == EXIT_CMD:
            log_str = 'exit'
        elif cmd_type == ATTR_OR_METHOD_CMD:
            log_str = 'check if this is a method or an attribute'
        else:
            raise ValueError('Unknown command : ' + cmd_type)

        self.logger.debug('Object proxy asking daemon to ' + log_str + ((': ' + meth_or_attr_name)
                                                                        if meth_or_attr_name is not None else ''))
        self.parent_conn.send((cmd_type, meth_or_attr_name, args, kwargs))

        if cmd_type == EXIT_CMD:
            return
        else:
            # wait for the results of the python method called
            res = self.parent_conn.recv()
            if res[0] == OK_FLAG:
                if cmd_type == ATTR_OR_METHOD_CMD:
                    str_to_log = meth_or_attr_name + (' is a method' if res[1] == METHOD_CMD else \
                        ('is an attribute' if res[1] == ATTR_CMD else 'is unknown: ' + str(res[1])))
                    self.logger.debug('Object proxy received response from daemon : ' + str_to_log)
                else:
                    self.logger.debug('Object proxy received response from daemon : ' + str(res[1]))
                return res[1]
            elif res[0] == ERR_FLAG:
                self.logger.debug('Object proxy received error from daemon : ' + str(res[1]))
                raise res[1]
            else:
                raise Exception('Unknown response flag received : ' + res[0] + '. Response body is ' + res[1])

    def __del__(self):
        """
        Callback to kill the sub process when this object is cleaned by the garbage collector (when no other
        object has pointers to it).
        :return:
        """
        # only do this if init was entirely completed.
        if self.is_started():
            self.terminate_daemon()

    def terminate_daemon(self):
        """
        terminates the daemon subprocess
        :return:
        """
        # call exit
        self.remote_call_using_pipe(EXIT_CMD)

        # set started to false to prevent future calls
        self.started = False

        # no need to close self.parent_conn - it is done automatically when garbage collected (see multiprocessing doc)

        # wait for child process termination
        self.p.join(timeout=10000)
        self.p.terminate()
        self.logger.info('Object proxy terminated successfully')


def daemon(conn, obj_instance_or_definition: Union[Any, InstanceDefinition]):
    """
    Implements a daemon connected to the multiprocessing Pipe provided as first argument.
    This daemon will
    * either reuse the object instance provided, or create an instance corresponding to the InstanceDefinition provided
    * dispatch to this instance any command received over the pipe, and return the results.

    Note that exceptions are correctly sent back too.

    :param conn: the pipe connection (on windows a PipeConnection instance, but behaviour is different on linux)
    :param obj_instance_or_definition: either an object instance to be used to execute the commands, or an
    InstanceDefinition to be used to instantiate the object locally.
    :return:
    """

    # default logger
    # TODO (even local import) does not work
    # import sys
    # from logging import getLogger, StreamHandler
    # _daemon_logger = getLogger('pyoad-daemon')
    # ch = StreamHandler(sys.stdout)
    # _daemon_logger.addHandler(ch)

    pid = str(os.getpid())
    exe = sys.executable  # str(os.path.abspath(os.path.join(os.__file__, '../..')))
    print_prefix = '[' + pid + '] Object daemon'
    print(print_prefix + ' started in : ' + exe)

    # --init implementation
    if isinstance(obj_instance_or_definition, InstanceDefinition):
        impl = obj_instance_or_definition.instantiate()
    else:
        impl = obj_instance_or_definition

    # --while there are incoming messages in the pipe, handle them
    while True:
        # retrieve next message (blocks until there is one)
        cmd_type, method_or_attr_name, method_args_list, method_kwargs_dct = conn.recv()
        if cmd_type == EXIT_CMD:
            print(print_prefix + '  was asked to exit - closing communication connection')
            conn.close()
            break
        else:
            exec_cmd_and_send_results(conn, print_prefix, impl, cmd_type,
                                      (method_or_attr_name, method_args_list, method_kwargs_dct))

    # out of the while loop
    print(print_prefix + '  terminating')


# type definition for the payload - fancy :)
CmdPayload = Tuple[str, List, Dict]


def exec_cmd_and_send_results(conn, print_prefix: str, impl: Any, cmd_type: int, cmd_body: CmdPayload):
    """
    Executes command of type cmd_type with payload cmd_body on object impl, and returns the results in the connection

    :param conn: the pipe connection (on windows a PipeConnection instance, but behaviour is different on linux)
    :param print_prefix:
    :param impl:
    :param cmd_type:
    :param cmd_body: the payload of the command to execute
    :return:
    """
    try:
        results = execute_cmd(print_prefix, impl, cmd_type, *cmd_body)

        # return results in communication pipe
        conn.send((OK_FLAG, results))

    except Exception as e:
        # return error in communication pipe
        conn.send((ERR_FLAG, e))


def execute_cmd(print_prefix: str, impl: Any, cmd_type: int,
                method_or_attr_name: str, method_args_list: List, method_kwargs_dict: Dict):
    """
    Executes command of type cmd_type on object impl. The following types of commands are available
    * ATTR_OR_METHOD_CMD: returns ATTR_CMD if the method_or_attr_name is a field of impl, or METHOD_CMD if it is a
    method of impl
    * ATTR_CMD: returns the value of field method_or_attr_name on object impl
    * METHOD_CMD: executed method method_or_attr_name on object impl, with arguments *method_args_list and
    **method_kwargs_dict

    :param print_prefix: the prefix to use in print messages
    :param impl: the object on which to execute the commands
    :param cmd_type: the type of command, in ATTR_OR_METHOD_CMD, METHOD_CMD, ATTR_CMD
    :param method_or_attr_name: the name of the method (METHOD_CMD) or attribute (ATTR_CMD), or both
    (ATTR_OR_METHOD_CMD)
    :param method_args_list: positional arguments for the method (METHOD_CMD only)
    :param method_kwargs_dict: keyword arguments for the method (METHOD_CMD only)
    :return:
    """

    if cmd_type == ATTR_OR_METHOD_CMD:
        # _daemon_logger.debug(print_prefix + ' was asked to check if this is a method or an attribute: ' + name)

        # check if this is a field or a method of impl
        if not callable(getattr(impl, method_or_attr_name)):
            return ATTR_CMD
        else:
            return METHOD_CMD

    elif cmd_type == METHOD_CMD:
        # _daemon_logger.debug(print_prefix + ' was asked to execute method: ' + method_or_attr_name)

        # execute method on implementation
        return getattr(impl, method_or_attr_name)(*method_args_list, **method_kwargs_dict)

    elif cmd_type == ATTR_CMD:
        # _daemon_logger.debug(print_prefix + ' was asked for attribute: ' + method_or_attr_name)

        # return implementation's field value
        return getattr(impl, method_or_attr_name)

    else:
        print(print_prefix + ' received unknown command : ' + cmd_type + '. Ignoring...')
