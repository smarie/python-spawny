import multiprocessing as mp
import os
from logging import Logger

import sys
from pickle import PicklingError
from types import FunctionType

from six import with_metaclass, raise_from

try: # python 3.5+
    from typing import Union, Any, List, Dict, Tuple, Type, Iterable, Callable
except SyntaxError:
    # strange error on some python 3.7 distributions ?!!
    pass
except ImportError:
    pass

from spawny.main_remotes_and_defs import InstanceDefinition, ScriptDefinition, ModuleDefinition, Definition
from spawny.utils_logging import default_logger
from spawny.utils_object_proxy import ProxifyDunderMeta, replace_all_dundermethods_with_getattr


PY2 = sys.version_info < (3, 0)


# def init_mp_context():
#     """  NOT SUPPORTED IN PYTHON 2
#     multiprocessing toolbox setup
#     :return:
#     """
#     mp.set_start_method('spawn')


def run_script(script_str,            # type: str
               python_exe=None,       # type: str
               logger=default_logger  # type: Logger
               ):
    # type: (...) -> ObjectProxy
    """
    Executes the provided script in a subprocess. The script will be run in a dynamically created module.

    Returns an instance of `DaemonProxy` representing the created module, that will transmit all interactions to the
    backend module through the created inter-process communication channel.

    :param script_str:
    :param python_exe:
    :param logger:
    :return:
    """
    d = DaemonProxy(ScriptDefinition(script_str), python_exe=python_exe, logger=logger)
    return d.obj_proxy


def run_module(module_name,           # type: str
               module_path=None,      # type: str
               python_exe=None,       # type: str
               logger=default_logger  # type: Logger
               ):
    # type: (...) -> ObjectProxy
    """
    Executes the provided module in a subprocess.

    Returns an instance of `DaemonProxy` representing the module, that will transmit all interactions to the
    backend module through the created inter-process communication channel.

    :param module_name:
    :param module_path:
    :param python_exe:
    :param logger:
    :return:
    """
    d = DaemonProxy(ModuleDefinition(module_name, module_path=module_path), python_exe=python_exe, logger=logger)
    return d.obj_proxy


def run_object(
               object_instance_or_definition,  # type: Union[Any, Definition]
               python_exe=None,                # type: str
               logger=default_logger           # type: Logger
               ):
    # type: (...) -> ObjectProxy
    d = DaemonProxy(object_instance_or_definition, python_exe=python_exe, logger=logger)
    return d.obj_proxy


# 'protocol' constants
OK_FLAG = True
ERR_FLAG = False
START_CMD = -1
EXIT_CMD = 0
EXEC_CMD = 1  # this will send a function to execute


# --------- all the functions that will be pickled so as to be remotely executed

def get_object(o,
               names
               ):
    """
    Command used to get the object o.name1.name2.name3 where name1, name2, name3 are provided in `names`
    It is located here so that it can be pickled and sent over the wire

    :param o:
    :param names:
    :return:
    """
    result = o
    for n in names:
        result = getattr(result, n)
    return result


def is_function(o,
                names):
    o = get_object(o, names)
    if isinstance(o, FunctionType):
        return True
    elif hasattr(o, 'im_self'):
        return True
    elif hasattr(o, '__self__'):
        return True
    else:
        return False


def call_method_on_object(o,
                          *args,
                          # names,
                          **kwargs):
    names = kwargs.pop('names')
    return get_object(o, names)(*args, **kwargs)


def call_method_using_cmp_py2(o,
                              *args,
                              # names,
                              # method_to_replace
                              **kwargs):
    """
    In python 2 some objects (int...) do not implement rich comparison.
    The problem is that the proxy that we create for them do implement it.
    So we have to redirect the implementation.
    See https://portingguide.readthedocs.io/en/latest/comparisons.html#rich-comparisons

    :param o:
    :param args:
    :param kwargs:
    :return:
    """
    names = kwargs.pop('names')
    method_to_replace = kwargs.pop('method_to_replace')
    cmp_result = get_object(o, names + ['__cmp__'])(*args, **kwargs)

    if method_to_replace == '__eq__':
        return cmp_result == 0
    elif method_to_replace == '__ne__':
        return cmp_result != 0
    elif method_to_replace == '__lt__':
        return cmp_result < 0
    elif method_to_replace == '__le__':
        return cmp_result <= 0
    elif method_to_replace == '__gt__':
        return cmp_result > 0
    elif method_to_replace == '__ge__':
        return cmp_result >= 0
    else:
        raise ValueError("invalid method: %s" % method_to_replace)

# ---------- end of picklable functions


class ObjectProxy(with_metaclass(ProxifyDunderMeta, object)):
    """
    Represents a proxy to an object. It relies on a daemon proxy to communicate.

    Thanks to the `ProxifyDunderMeta` metaclass, all dunder methods are redirected to __getattr__. See  https://stackoverflow.com/questions/9057669/how-can-i-intercept-calls-to-pythons-magic-methods-in-new-style-classes


    """
    __ignore__ = "class mro new init setattr getattr getattribute dict del dir doc name qualname module"

    __myslots__ = 'daemon', 'is_multi_object', 'child_names'  # 'instance_type',

    def __init__(self,
                 daemon,              # type: DaemonProxy
                 is_multi_object,     # type: bool
                 instance_type=None,  # type: Type[Any]
                 #attr_methods=None,   # type: List[str]
                 child_names=None     # type: List[str]
                 ):

        to_ignore = set("__%s__" % n for n in ObjectProxy.__ignore__.split())

        # replace all methods dynamically: actually this seems to be useless since if we do not do it
        # at class creation that's not taken into account by python.
        if instance_type is not None:
            # if attr_methods is not None:
            #     raise ValueError("only one of instance_type or attr_methods must be set")
            replace_all_dundermethods_with_getattr(ignore=to_ignore, from_cls=instance_type, to_cls_or_inst=self,
                                                   is_class=False)
        # else:
        #     if attr_methods is None:
        #         raise ValueError("one of instance_type or attr_methods must be set")
        #     replace_all_methods_with_getattr(ignore=to_ignore, from_cls=attr_methods, to_cls_or_inst=self,
        #                                      is_class=False)

        self.daemon = daemon
        # self.instance_type = instance_type
        self.is_multi_object = is_multi_object
        self.child_names = child_names

    def __getattr__(self, item):
        if item in ObjectProxy.__myslots__:
            # real local attributes
            return super(ObjectProxy, self).__getattribute__(item)
        elif item in ('terminate_daemon', ):
            # real daemon attributes
            return getattr(self.daemon, item)
        else:
            # remote communication
            if self.child_names is not None:
                names = self.child_names + [item]
            else:
                names = [item]

            # first let's check what kind of object this is so that we can determine what to do
            try:
                is_func = self.daemon.remote_call_using_pipe(EXEC_CMD, is_function, names=names, log_errors=False)
            except AttributeError as e:
                # Rich comparison operators might be missing
                if PY2 and item in ('__eq__', '__ne__', '__lt__', '__le__', '__gt__', '__ge__'):
                    def remote_method_proxy(*args, **kwargs):
                        return self.daemon.remote_call_using_pipe(EXEC_CMD, call_method_using_cmp_py2,
                                                                  to_execute_args=args, names=names[0:-1],
                                                                  method_to_replace=item, **kwargs)
                    return remote_method_proxy
                else:
                    raise_from(e, e)

            if is_func:
                # a function (not a callable object ): generate a remote method proxy with that name
                def remote_method_proxy(*args, **kwargs):
                    return self.daemon.remote_call_using_pipe(EXEC_CMD, call_method_on_object,
                                                              to_execute_args=args, names=names, **kwargs)

                return remote_method_proxy

            else:
                # an object
                try:
                    typ = self.daemon.remote_call_using_pipe(EXEC_CMD, get_object, names=names + ['__class__'],
                                                             log_errors=False)

                    if self.is_multi_object:
                        # create a new DaemonProxy for that object
                        return ObjectProxy(self.daemon, instance_type=typ, is_multi_object=False, child_names=names)
                    else:
                        # bring back the attribute value over the pipe
                        return self.daemon.remote_call_using_pipe(EXEC_CMD, get_object, names=names)

                except PicklingError as pe:
                    # the object type is not known or cant be decoded locally.
                    # TODO get the list of methods ?
                    return ObjectProxy(self.daemon, instance_type=None, is_multi_object=False, child_names=names)

    # TODO
    # def __setattr__(self, key, value):
    #     if not self.is_started():
    #         return super(DaemonProxy, self).__setattr__(key, value)
    #     else:
    #         return setattr(self.obj_proxy, key, value)

    def __call__(self, *args, **kwargs):
        return self.daemon.remote_call_using_pipe(EXEC_CMD, call_method_on_object, names=self.child_names,
                                                  to_execute_args=args, **kwargs)


class CommChannel(object):
    __slots__ = 'conn',

    def __init__(self, conn):
        self.conn = conn

    def __del__(self):
        self.conn = None


class DaemonProxy(object):
    """
    A proxy that spawns (or TODO conects to)
    a separate process and delegates the methods to it, through an `ObjectProxy`.
    """
    def __init__(self,
                 obj_instance_or_definition,  # type: Union[Any, Definition]
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
        if isinstance(obj_instance_or_definition, Definition):
            instance_type = obj_instance_or_definition.get_type()
            is_multi_object = obj_instance_or_definition.is_multi_object()
        else:
            instance_type = obj_instance_or_definition.__class__
            is_multi_object = False

        self.obj_proxy = ObjectProxy(daemon=self, instance_type=instance_type, is_multi_object=is_multi_object)

        # --set executable (actually there is no way to ensure that this is atomic with mp.Process(), too bad !
        if python_exe is not None:
            if sys.version_info < (3, 0) and not sys.platform.startswith('win'):
                raise ValueError("`python_exe` can only be set on windows under python 2. See "
                                 "https://docs.python.org/2/library/multiprocessing.html#multiprocessing.")
            else:
                mp.set_executable(python_exe)

        # --init the multiprocess communication queue/pipe
        parent_conn, child_conn = mp.Pipe()
        self.parent_conn = CommChannel(parent_conn)
        # self.logger.info('Object proxy created an interprocess communication channel')

        # --spawn an independent process
        self.logger.info('[DaemonProxy] spawning child process...')
        self.p = mp.Process(target=daemon, args=(child_conn, obj_instance_or_definition),
                            name=python_exe or 'python' + '-' + str(obj_instance_or_definition))
        self.p.start()
        # make sure that instantiation happened correctly, and report possible exception otherwise
        self.wait_for_response()
        self.logger.info('[DaemonProxy] spawning child process... DONE. PID=%s' % (self.p.pid))
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

    def remote_call_using_pipe(self,
                               cmd_type,              # type: int
                               to_execute=None,       # type: Callable[[Any], Any]
                               to_execute_args=None,  # type: Iterable[Any]
                               log_errors=True,       # type: bool
                               **to_execute_kwargs    # type: Dict[str, Any]
                               ):
        """
        Calls a remote method

        Unfortunately there is no easy and portable way to transmit lambda functions over the wire so
        - to execute should be defined at the module level here
        - and what will be executed remotely is to_execute(o, **to_execute_kwargs)

        :param cmd_type: command type (EXIT_CMD, EXEC_CMD)
        :param to_execute:
        :return:
        """
        if not self.is_started():
            raise Exception('[%s] Cannot perform remote calls - daemon is not started' % self)

        if cmd_type == EXEC_CMD:
            log_str = 'execute method'
        elif cmd_type == EXIT_CMD:
            log_str = 'exit'
        else:
            raise ValueError('[%s] Invalid command : %s' % (self, cmd_type))

        query_str = log_str + ((': %s(o, *%s, **%s)' % (to_execute.__name__, to_execute_args, to_execute_kwargs))
                               if to_execute is not None else '')
        self.logger.debug('[%s] asking daemon to %s' % (self, query_str))
        self.parent_conn.conn.send((cmd_type, to_execute, to_execute_args, to_execute_kwargs))

        if cmd_type == EXIT_CMD:
            return
        else:
            # wait for the results of the python method called
            return self.wait_for_response(log_errors=log_errors)

    def wait_for_response(self,
                          log_errors=True):
        """
        Waits for a response from child process

        :return:
        """
        res = self.parent_conn.conn.recv()
        if res[0] == OK_FLAG:
            self.logger.debug('[%s] Received response from daemon: %s' % (self, res[1]))
            return res[1]
        elif res[0] == ERR_FLAG:
            if log_errors:
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
    # _daemon_logger = getLogger('spawny-daemon')
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
            cmd_type, to_execute, to_execute_args, to_execute_kwargs = conn.recv()
            if cmd_type == EXIT_CMD:
                print(print_prefix + '  was asked to exit - closing communication connection')
                conn.close()
                break
            else:
                try:
                    if to_execute_args is None:
                        to_execute_args = ()

                    if to_execute_kwargs is not None:
                        results = to_execute(impl, *to_execute_args, **to_execute_kwargs)
                    else:
                        results = to_execute(impl, *to_execute_args)

                    # return results in communication pipe
                    conn.send((OK_FLAG, results))
                except Exception as e:
                    # return error in communication pipe
                    conn.send((ERR_FLAG, e))

    finally:
        # out of the while loop
        print(print_prefix + '  terminating')


# def exec_cmd_and_send_results(conn,
#                               impl,           # type: Any
#                               to_execute      # type: Callable[[Any], Any]
#                               ):
#     """
#     Executes command of type cmd_type with payload cmd_body on object impl, and returns the results in the connection
#
#     :param conn: the pipe connection (on windows a PipeConnection instance, but behaviour is different on linux)
#     :param impl:
#     :param to_execute: the function to execute on the object
#     :return:
#     """
#     try:
#         results = to_execute(impl)
#     except Exception as e:
#         # return error in communication pipe
#         conn.send((ERR_FLAG, e))
#     else:
#         # return results in communication pipe
#         conn.send((OK_FLAG, results))


# def execute_cmd(print_prefix,          # type: str
#                 impl,                  # type: Any
#                 cmd_type,              # type: int
#                 method_or_attr_names,  # type: List[Reference]
#                 method_args_list,      # type: List
#                 method_kwargs_dict     # type: Dict
#                 ):
#     """
#     Executes command of type cmd_type on object impl. The following types of commands are available
#
#      * ATTR_OR_METHOD_CMD: returns ATTR_CMD if the method_or_attr_name is a field of impl, or METHOD_CMD if it is a
#        method of impl
#      * ATTR_CMD: returns the value of field method_or_attr_name on object impl
#      * METHOD_CMD: executed method method_or_attr_name on object impl, with arguments *method_args_list and
#        **method_kwargs_dict
#
#     :param print_prefix: the prefix to use in print messages
#     :param impl: the object on which to execute the commands
#     :param cmd_type: the type of command, in ATTR_OR_METHOD_CMD, METHOD_CMD, ATTR_CMD
#     :param method_or_attr_names: a list containing the qualified name of the method (METHOD_CMD) or attribute
#         (ATTR_CMD), or both (ATTR_OR_METHOD_CMD)
#     :param method_args_list: positional arguments for the method (METHOD_CMD only)
#     :param method_kwargs_dict: keyword arguments for the method (METHOD_CMD only)
#     :return:
#     """
#     method_or_attr = resolve_reference(impl, method_or_attr_names)
#
#     if cmd_type == METHOD_CMD:
#         # _daemon_logger.debug(print_prefix + ' was asked to execute method: ' + method_or_attr_name)
#
#         # execute method on implementation
#         method_args_list = [resolve_reference(impl, a) for a in method_args_list]
#         return method_or_attr(*method_args_list, **method_kwargs_dict)
#
#     elif cmd_type == ATTR_CMD:
#         # _daemon_logger.debug(print_prefix + ' was asked for attribute: ' + method_or_attr_name)
#
#         # return implementation's field value
#         return method_or_attr
#
#     else:
#         print(print_prefix + ' received unknown command : %s. Ignoring...' % cmd_type)
#
#
# class RemoteReference(object):
#     __slots__ = 'refs',
#
#     def __init__(self, refs):
#         self.refs = refs
#
#     def __str__(self):
#         return repr(self)
#
#     def __repr__(self):
#         return "Remote Reference %s" % self.refs
#
#
# def resolve_reference(impl,
#                       any_or_reference  # type: Union[Any, RemoteReference]
#                       ):
#     """
#     If any_or_reference is a reference, resolve it with respect to `impl`.
#     Otherwise return it as is.
#
#     :param impl:
#     :param any_or_reference:
#     :return:
#     """
#     if isinstance(any_or_reference, RemoteReference):
#         method_or_attr = impl
#         for elt in any_or_reference.refs:
#             method_or_attr = getattr(method_or_attr, elt)
#         return method_or_attr
#     else:
#         return any_or_reference
