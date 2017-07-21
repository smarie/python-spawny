import subprocess

from os import path
from io import StringIO

import pytest

from pyoad import init_mp_context, ObjectDaemonProxy

THIS_DIR = path.dirname(path.abspath(__file__))


# --init multiprocessing context to be used in vs_impl fixture
init_mp_context()


def create_temporary_venv(env_name: str, py_version: str):
    """
    Creates a temporary virtual environment with the provided python version

    :param env_name:
    :param py_version:
    :return:
    """
    env_path = path.abspath(path.join(THIS_DIR, '../..', 'tmp_venv', env_name))

    # Create virtual environment
    if not path.isdir(env_path):
        cmd = ['conda', 'create', '--prefix', env_path, 'python=' + py_version, '--yes']
        print('Creating Test virtual environment : ' + ' '.join(cmd))
        subprocess.run(cmd)
        print('Test virtual environment created')
    else:
        print('Test virtual environment already exists')
    return path.join(env_path, 'python.exe')


def test_mini():
    daemon_strio = ObjectDaemonProxy('io', 'StringIO', 'hello, world!')
    print(daemon_strio.getvalue())


TEST_STR = 'str\nhello'


def test_main():

    # --create temporary new python environment
    python_exe = create_temporary_venv('tmp', '3.5.0')

    # try locally to be sure our test is correct
    print('local test')
    o_l = StringIO(TEST_STR)
    perform_test_actions(o_l)

    # create daemon object
    print('daemon test')
    o_r = ObjectDaemonProxy('io', 'StringIO', TEST_STR, python_exe=python_exe)
    perform_test_actions(o_r)


def perform_test_actions(strio_obj: StringIO):
    # --test get_value
    assert strio_obj.getvalue() == TEST_STR

    # --test write
    strio_obj.write('**')
    new_test_str = '**' + TEST_STR[2:]
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
