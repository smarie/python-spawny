import multiprocessing as mp
import os
from logging import Logger

import sys

from six import with_metaclass

try: # python 3.5+
    from typing import Union, Any, List, Dict, Tuple

    # type definition for the payload - fancy :)
    CmdPayload = Tuple[str, List, Dict]
except ImportError:
    pass

from spawner.main_remotes_and_defs import InstanceDefinition, ScriptDefinition, ModuleDefinition
from spawner.utils_logging import default_logger
from spawner.utils_object_proxy import ProxifyDunderMeta, replace_all_dundermethods_with_getattr


# def init_mp_context():
#     """  NOT SUPPORTED IN PYTHON 2
#     multiprocessing toolbox setup
#     :return:
#     """
#     mp.set_start_method('spawn')


# 'protocol' constants
OK_FLAG = True
ERR_FLAG = False
START_CMD = -1
EXIT_CMD = 0
ATTR_OR_METHOD_CMD = 1
METHOD_CMD = 2
ATTR_CMD = 3


class DaemonProxy(with_metaclass(ProxifyDunderMeta, object)):
    """
    A proxy that spawns (or TODO conects to)
    a separate process and delegates the methods to it.

    For the trick about redirecting all dunder methods to getattr, see
    https://stackoverflow.com/questions/9057669/how-can-i-intercept-calls-to-pythons-magic-methods-in-new-style-classes
    """

    __ignore__ = "class mro new init setattr getattr getattribute dict del dir doc name qualname module"

    def __init__(self,
                 obj_instance_or_definition,  # type: Union[Any, InstanceDefinition, ScriptDefinition]
                 python_exe=None,             # type: str
                 logger=default_logger        # type: Logger
                 ):
        # type: (...) -> DaemonProxy
        """
        Creates a daemon running the provided object instance, and inits this Proxy to be able to delegate the calls to
        the daemon. Users may either provide the object instance, or a definition of instance to create. In that case
        the instance will be created in the daemon.

        :param obj_instance_or_definition: the object instance to use in the daemon, or the definition that the daemon
            should follow to create the object instance
        :param python_exe: the optional python executable to use to launch the daemon. By default the same executable
            than this process will be used. Note that a non-None value is not supported on python 2 if the system is
            not windows
        :param logger: an optional custom logger. By default a logger that prints to stdout will be used.
        """
        self.started = False
        self.logger = logger or default_logger

        # --proxify all dunder methods from the instance type
        # unfortunately this does not help much since for new-style classes, special methods are only looked up on the
        # class not the instance. That's why we try to register as much special methods as possible in ProxifyDunderMeta
        instance_type = obj_instance_or_definition.get_type() \
            if isinstance(obj_instance_or_definition, InstanceDefinition) else type(obj_instance_or_definition)
        replace_all_dundermethods_with_getattr(set("__%s__" % n for n in DaemonProxy.__ignore__.split()),
                                               instance_type, self, is_class=False)

        # --set executable (actually there is no way to ensure that this is atomic with mp.Process(), too bad !
        if python_exe is not None:
            if sys.version_info < (3, 0) and not sys.platform.startswith('win'):
                raise ValueError("`python_exe` can only be set on windows under python 2. See "
                                 "https://docs.python.org/2/library/multiprocessing.html#multiprocessing.")
            mp.set_executable(python_exe)

        # --init the multiprocess communication queue/pipe
        self.parent_conn, child_conn = mp.Pipe()
        # self.logger.info('Object proxy created an interprocess communication channel')

        # --spawn an independent process
        self.logger.info('[%s] spawning Child process for object daemon...' % self)
        self.p = mp.Process(target=daemon, args=(child_conn, obj_instance_or_definition),
                            name=python_exe or 'python' + '-' + str(obj_instance_or_definition))
        self.p.start()
        # make sure that instantiation happened correctly, and report possible exception otherwise
        self.wait_for_response(START_CMD)
        self.logger.info('[%s] spawning Child process for object daemon... DONE. PID=%s' % (self, self.p.pid))
        self.started = True

    def is_started(self):
        return self.started

    def __str__(self):
        return repr(self)

    def __repr__(self):
        if not self.is_started():
            return 'DaemonProxy<not started>'
        else:
            return 'DaemonProxy<%s>' % self.p.pid

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

    def remote_call_using_pipe(self,
                               cmd_type,                # type: int
                               meth_or_attr_name=None,  # type: str
                               *args,
                               **kwargs
                               ):
        """
        Calls a remote method

        :param cmd_type: command type (EXIT_CMD, METHOD_CMD, ATTR_CMD)
        :param meth_or_attr_name:
        :param args:
        :param kwargs:
        :return:
        """
        if not self.is_started():
            raise Exception('[%s] Cannot perform remote calls - daemon is not started' % self)

        if cmd_type == METHOD_CMD:
            log_str = 'execute method'
        elif cmd_type == ATTR_CMD:
            log_str = 'access attribute'
        elif cmd_type == EXIT_CMD:
            log_str = 'exit'
        elif cmd_type == ATTR_OR_METHOD_CMD:
            log_str = 'check if this is a method or an attribute'
        else:
            raise ValueError('[%s] Invalid command : %s' % (self, cmd_type))

        query_str = log_str + ((': ' + meth_or_attr_name) if meth_or_attr_name is not None else '')
        self.logger.debug('[%s] asking daemon to %s' % (self, query_str))
        self.parent_conn.send((cmd_type, meth_or_attr_name, args, kwargs))

        if cmd_type == EXIT_CMD:
            return
        else:
            # wait for the results of the python method called
            return self.wait_for_response(cmd_type, meth_or_attr_name)

    def wait_for_response(self, cmd_type, meth_or_attr_name=None):
        """
        Waits for a response from chil process

        :param cmd_type:
        :param meth_or_attr_name:
        :return:
        """
        res = self.parent_conn.recv()
        if res[0] == OK_FLAG:
            if cmd_type == ATTR_OR_METHOD_CMD:
                str_to_log = meth_or_attr_name \
                             + (' is a method' if res[1] == METHOD_CMD else
                                ('is an attribute' if res[1] == ATTR_CMD else 'is unknown: ' + str(res[1])))
                self.logger.debug('[%s] Received response from daemon: %s' % (self, str_to_log))
            else:
                self.logger.debug('[%s] Received response from daemon: %s' % (self, res[1]))
            return res[1]
        elif res[0] == ERR_FLAG:
            self.logger.warning('[%s] Received error from daemon: %s' % (self, res[1]))
            raise res[1]
        else:
            raise Exception('[%s] Unknown response flag received: %s. Response body is %s' % (self, res[0], res[1]))

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
        self_repr = repr(self)

        # call exit
        self.remote_call_using_pipe(EXIT_CMD)

        # set started to false to prevent future calls
        self.started = False

        # no need to close self.parent_conn - it is done automatically when garbage collected (see multiprocessing doc)

        # wait for child process termination
        self.p.join(timeout=10000)
        self.p.terminate()
        self.logger.info('[%s] Terminated successfully' % self_repr)


ObjectDaemonProxy = DaemonProxy
"""Old alias"""


def daemon(conn,
           obj_instance_or_definition,  # type: Union[Any, InstanceDefinition, ScriptDefinition]
           ):
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
    # _daemon_logger = getLogger('spawner-daemon')
    # ch = StreamHandler(sys.stdout)
    # _daemon_logger.addHandler(ch)

    pid = str(os.getpid())
    exe = sys.executable  # str(os.path.abspath(os.path.join(os.__file__, '../..')))
    print_prefix = '[' + pid + '] Daemon'
    print(print_prefix + ' started using python interpreter: ' + exe)

    try:
        # --init implementation
        if isinstance(obj_instance_or_definition, InstanceDefinition):
            impl = obj_instance_or_definition.instantiate()
        elif isinstance(obj_instance_or_definition, ScriptDefinition):
            impl = obj_instance_or_definition.execute()
        elif isinstance(obj_instance_or_definition, ModuleDefinition):
            impl = obj_instance_or_definition.execute()
        else:
            # the object was entirely transfered on the wire by the client.
            impl = obj_instance_or_definition

    except Exception as e:
        conn.send((ERR_FLAG, e))

    else:
        # declare that we are correctly started
        conn.send((OK_FLAG, "%s started" % print_prefix))

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

    finally:
        # out of the while loop
        print(print_prefix + '  terminating')


def exec_cmd_and_send_results(conn,
                              print_prefix,   # type: str
                              impl,           # type: Any
                              cmd_type,       # type: int
                              cmd_body        # type: CmdPayload
                              ):
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


def execute_cmd(print_prefix,         # type: str
                impl,                 # type: Any
                cmd_type,             # type: int
                method_or_attr_name,  # type: str
                method_args_list,     # type: List
                method_kwargs_dict    # type: Dict
                ):
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
        print(print_prefix + ' received unknown command : %s. Ignoring...' % cmd_type)
