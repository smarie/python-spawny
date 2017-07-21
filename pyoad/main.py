import multiprocessing as mp
import os
from importlib import import_module
from logging import Logger
from multiprocessing.connection import PipeConnection

import sys
from warnings import warn

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
METHOD_CMD = 1
ATTR_CMD = 2


# default logger
_default_logger = logging.getLogger('pyoad')
ch = logging.StreamHandler(sys.stdout)
_default_logger.addHandler(ch)


# TODO maybe it is possible to actually send the initial object to the daemon. Not sure why it would be interesting..


class ObjectDaemonProxy(object):
    """
    A proxy that spawns a separate process and delegates the methods to it
    """

    def __init__(self, module_name: str, clazz_name: str, *args, no_local_inst: bool = False, python_exe: str = None,
                 logger: Logger = _default_logger, **kwargs):
        """
        Creates a daemon and inits the proxy object

        :param python_exe:
        :param module_name:
        :param clazz_name:
        :param no_local_inst: if True, the proxy object will not create a local instance of the object for the purpose
        of knowing if an attr is a method or a field. If True, only methods can be used on remote objects.
        :param args: positional arguments for the object constructor
        :param kwargs: keyword arguments for the object constructor
        """

        self.logger = logger or _default_logger

        # --set executable (actually there is no way to ensure that this is atomic with mp.Process(), too bad !
        if python_exe is not None:
            mp.set_executable(python_exe)

        # --init the multiprocess communication queue/pipe
        self.parent_conn, child_conn = mp.Pipe()
        self.logger.info('Object proxy created an interprocess communication channel')

        # --spawn an independent process
        self.logger.info('Object proxy spawning Child process for object daemon')
        self.p = mp.Process(target=daemon, args=(child_conn, module_name, clazz_name, no_local_inst, args, kwargs),
                            name=python_exe or 'python' + '-' + module_name + '.' + clazz_name + '(' + str(args) + str(kwargs) + ')')
        self.p.start()

        self.no_local_inst = no_local_inst
        if not no_local_inst:
            self.inst = instantiate(module_name, clazz_name, *args, **kwargs)

    def __getattr__(self, name):
        """
        Dynamic proxy

        :param name:
        :return:
        """
        if not self.no_local_inst:
            # use the local instance to check if we're asked for a method or a field
            if not callable(getattr(self.inst, name)):
                # return an attribute value
                return self.remote_call_using_pipe(ATTR_CMD, name)

        # generate a remote method proxy with that name
        def remote_method_proxy(*args, **kwargs):
            return self.remote_call_using_pipe(METHOD_CMD, name, *args, **kwargs)

        return remote_method_proxy

    def remote_call_using_pipe(self, cmd_type, method_name: str = None, *args, **kwargs):
        """
        Calls a remote method

        :param cmd_type: command type (EXIT_CMD, METHOD_CMD, ATTR_CMD)
        :param method_name:
        :param args:
        :param kwargs:
        :return:
        """
        log_str = 'execute method' if cmd_type == METHOD_CMD else ('access attribute'
                                                                   if cmd_type == ATTR_CMD else 'exit')
        self.logger.debug('Object proxy asking daemon to ' + log_str + ((': ' + method_name)
                                                                        if method_name is not None else ''))
        self.parent_conn.send((cmd_type, method_name, args, kwargs))

        if cmd_type == EXIT_CMD:
            return
        else:
            # wait for the results of the python method called
            res = self.parent_conn.recv()
            self.logger.debug('Object proxy received response from daemon ' + str(res))
            if res[0] == OK_FLAG:
                return res[1]
            elif res[0] == ERR_FLAG:
                raise res[1]
            else:
                raise Exception('Unknown response flag received : ' + res[0] + '. Response body is ' + res[1])

    def __del__(self):
        """
        Callback to kill the sub process when this object is cleaned by the garbage collector (when no other
        object has pointers to it).
        :return:
        """
        self.terminate_daemon()

    def terminate_daemon(self):
        """
        terminates the daemon subprocess
        :return:
        """
        # call exit
        self.remote_call_using_pipe(EXIT_CMD)

        # no need to close the connection - it is done automatically when garbage collected (see doc)

        # wait for child process termination
        self.p.join(timeout=10000)
        self.p.terminate()
        self.logger.info('Object proxy terminated successfully')


def daemon(conn: PipeConnection, module_name: str, clazz_name: str, disable_fields: bool, args, kwargs):
    """
    Implements a daemon connected to the multiprocessing Pipe provided as first argument.
    This daemon will
    * create an instance of <module_name>.<clazz_name> using args and kwargs in the constructor
    * dispatch to this instance any command received over the pipe, and return the results.

    :param conn:
    :param module_name:
    :param clazz_name:
    :param disable_fields: if True only methods can be called
    :param args: a list of positional arguments for the object constructor
    :param kwargs: a dict of keyword arguments for the object constructor
    :return:
    """

    # default logger
    # TODO even this does not work
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
    # exec(import_str) was too unsafe
    impl = instantiate(module_name, clazz_name, *args, **kwargs)

    # --while there are incoming messages in the pipe, handle them
    while True:
        # retrieve next message (blocks until there is one)
        cmd, method_or_attr_name, method_args_list, method_kwargs_dict = conn.recv()

        if cmd == METHOD_CMD:
            # _daemon_logger.debug(print_prefix + ' was asked to execute method: ' + method_or_attr_name)
            try:
                # execute method on implementation
                results = getattr(impl, method_or_attr_name)(*method_args_list, **method_kwargs_dict)

                # return results in communication pipe
                conn.send((OK_FLAG, results))

            except Exception as e:
                # return results in communication pipe
                conn.send((ERR_FLAG, e))

        elif cmd == ATTR_CMD:
            # _daemon_logger.debug(print_prefix + ' was asked for attribute: ' + method_or_attr_name)
            if disable_fields:
                warn('Accessing attribute ' + method_or_attr_name + ' is not allowed - only methods '
                                        'are allowed on this daemon')
            else:
                try:
                    # execute method on implementation
                    results = getattr(impl, method_or_attr_name)

                    # return results in communication pipe
                    conn.send((OK_FLAG, results))

                except Exception as e:
                    # return results in communication pipe
                    conn.send((ERR_FLAG, e))

        elif cmd == EXIT_CMD:
            # we received EXIT command
            print(print_prefix + '  was asked to exit - closing communication connection')
            conn.close()
            break

        else:
            print(print_prefix + ' received unknown command : ' + cmd + '. Ignoring...')

    # out of the while loop
    print(print_prefix + '  terminating')


def instantiate(module_name: str, clazz_name: str, *args, **kwargs):
    """
    Utility method to instantiate an object of class clazz_name in module module_name. Submodules are supported, simply
    add them with the dot notation in the module name as in 'os.path'

    :param module_name:
    :param clazz_name:
    :param args:
    :param kwargs:
    :return:
    """
    m = import_module(module_name)
    clazz = getattr(m, clazz_name)
    impl = clazz(*args, **kwargs)
    return impl
