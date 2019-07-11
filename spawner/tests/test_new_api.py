import sys
from collections import OrderedDict
from os.path import join, dirname

from spawner import run_script, run_module


def test_remote_script():
    """ Simple test with daemon-side instantiation of a io.StringIO """

    script = """
from collections import OrderedDict

odct = OrderedDict()
odct['a'] = 1

foo = "hello world"

def say_hello(who):
    return "hello, %s!" % who

print(say_hello("process"))    
"""

    remote_script = run_script(script)

    try:
        assert remote_script.odct == OrderedDict([('a', 1)])
        assert remote_script.foo == "hello world"
        assert remote_script.say_hello("earthling") == "hello, earthling!"
    finally:
        remote_script.terminate_daemon()


RESOURCES_DIR = join(dirname(__file__), 'resources')
NOT_IN_PATH_RESOURCES_DIR = join(RESOURCES_DIR, 'not_in_path')


def test_remote_module_from_name():
    """ Simple test with daemon-side instantiation of a io.StringIO """

    # named import
    sys.path.insert(0, RESOURCES_DIR)
    remote_script = run_module(module_name='dummy')

    try:
        assert remote_script.odct == OrderedDict([('a', 1)])
        assert remote_script.foo == "hello world"
        assert remote_script.say_hello("earthling") == "hello, earthling!"
    finally:
        remote_script.terminate_daemon()


def test_remote_module_from_path():
    """ Simple test with daemon-side instantiation of a io.StringIO """

    # path import
    remote_script = run_module('dummy2', module_path=join(NOT_IN_PATH_RESOURCES_DIR, 'dummy2.py'))

    try:
        assert remote_script.odct == OrderedDict([('a', 1)])
        assert remote_script.foo == "hello world"
        assert remote_script.say_hello("earthling") == "hello, earthling!"
    finally:
        remote_script.terminate_daemon()
