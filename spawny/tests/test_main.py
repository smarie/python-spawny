import subprocess
import sys

from os import path, makedirs

try:  # python 2
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import psutil
import pytest

from spawny import InstanceDefinition, run_object

THIS_DIR = path.dirname(path.abspath(__file__))


# @pytest.fixture(scope='session', autouse=True)
# def multiprocessing_fixture():
#     # init the multiprocessing engine so that "spawn" is the default way to kill a process
#     init_mp_context()
#     yield


def test_mini_instance_def():
    """ Simple test with daemon-side instantiation of a io.StringIO """
    daemon_strio = run_object(InstanceDefinition(StringIO.__module__, 'StringIO', 'hello, world!'))
    try:
        print(daemon_strio.getvalue())
    finally:
        daemon_strio.terminate_daemon()


def test_mini_instance_def_primitives():
    """ Simple test with daemon-side instantiation of a primitive (a str) """
    daemon_str = run_object(InstanceDefinition('builtins', 'str', 'hello, world!'))
    try:
        print(daemon_str)
    finally:
        daemon_str.terminate_daemon()


def test_mini_instance():
    """ Simple test with client-side instantiation of a str and transfer to the daemon """
    daemon_strio = run_object('hello, world!')
    try:
        print(daemon_strio)  # str then repr
        print('Explicit str required: ' + str(daemon_strio))  # str
        print('With str formatting:  %s  ' % daemon_strio)
        print('Explicit repr: ' + repr(daemon_strio))
        print('Subscript: ' + daemon_strio[0:5])
    finally:
        daemon_strio.terminate_daemon()


@pytest.mark.skipif(sys.version_info < (3, 0) and not sys.platform.startswith('win'),
                    reason="requires python3 or higher because `set_executable` is only available on windows for "
                           "python 2")
def test_main():
    """ Spawns a io.StringIO daemon in a temporary venv and asserts that it behaves exactly like a local instance """

    # --create temporary new python environment
    python_exe = _create_temporary_venv('tmp', ".".join(["%s" % s for s in sys.version_info[0:2]]))

    TEST_STR = 'str\nhello'

    # try locally to be sure our test is correct
    print('local test')
    o_l = StringIO(TEST_STR)
    perform_test_actions(o_l, TEST_STR)

    # create daemon object
    print('daemon test')
    o_r = run_object(InstanceDefinition(StringIO.__module__, 'StringIO', TEST_STR), python_exe=python_exe)
    try:
        perform_test_actions(o_r, TEST_STR)
    finally:
        o_r.terminate_daemon()


def perform_test_actions(strio_obj,  # type: StringIO
                         ref_str):
    # --test get_value
    assert strio_obj.getvalue() == ref_str

    # --test write
    strio_obj.write('**')
    new_test_str = '**' + ref_str[2:]
    assert strio_obj.getvalue() == new_test_str

    # --test readlines
    # first reinit the current index in the buffer
    strio_obj.seek(0)
    for a, b in zip(strio_obj.readlines(), new_test_str.splitlines()):
        assert a.replace('\n', '') == b

    # --test close
    strio_obj.close()
    with pytest.raises(ValueError):
        print(strio_obj.getvalue())


def teardown_module(module):
    """
    Make sure that gc runs at least once explicitly at the end of the test suite, so that no stale process remains.
    This happens sometimes in Travis CI
    """
    print('tearing down')
    import gc
    gc.collect()

    # you may wish to create this object to check that the termination code works, but warning: in debug mode,
    # the debugger will call its str() method after each step to refresh the 'variables' panel > might lock.
    # o_r = run_object('to_terminate')

    def on_terminate(proc):
        print("process {} terminated with exit code {}".format(proc, proc.returncode))

    procs = psutil.Process().children()
    for p in procs:
        p.terminate()

    gone, still_alive = psutil.wait_procs(procs, timeout=3, callback=on_terminate)
    for p in still_alive:
        p.kill()

    print('DONE')


def _create_temporary_venv(env_name,   # type: str
                           py_version  # type: str
                           ):
    """
    Creates a temporary virtual environment with the provided python version

    :param env_name:
    :param py_version:
    :return:
    """
    env_path = path.abspath(path.join(THIS_DIR, '../..', 'tmp_venv', env_name))

    # make sure that the root dir exists
    env_root_path = path.abspath(path.join(env_path, path.pardir))
    if not path.exists(env_root_path):
        makedirs(env_root_path)

    # Create virtual environment
    if not path.exists(env_path):
        try:
            cmd = ['conda', 'create', '--prefix', '"%s"' % env_path, 'python=%s' % py_version, '--yes']
            print('Creating Test virtual environment with conda: ' + ' '.join(cmd))
            # NOTE: conda needs to be on the path !
            subprocess.check_call(' '.join(cmd), shell=True)
            print('Test virtual environment created')
        except:
            if sys.version_info >= (3, 3):
                venv_module_name = 'venv'
            else:
                venv_module_name = 'virtualenv'
            cmd = ['python', '-m', venv_module_name, '"%s"' % env_path]
            print('Conda does not seem to be available. Creating Test virtual environment with venv (selected version '
                  'number will be ignored): ' + ' '.join(cmd))
            subprocess.check_call(' '.join(cmd), shell=True)
            print('Test virtual environment created')
    else:
        print('Test virtual environment already exists')

    if path.exists(path.join(env_path, 'python.exe')):
        # conda
        print('Test virtual environment is conda')
        python_exe = path.join(env_path, 'python.exe')
    else:
        # venv
        print('Test virtual environment is venv')
        python_exe = path.join(env_path, 'scripts', 'python.exe')
    return python_exe
