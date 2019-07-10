import sys
from collections import OrderedDict
from os.path import pardir, join

from spawner import ScriptDefinition, DaemonProxy, ModuleDefinition


def test_remote_script():
    """ Simple test with daemon-side instantiation of a io.StringIO """

    script = """
from collections import OrderedDict

odct = OrderedDict()
odct['a'] = 1

foo = "hello world"
"""

    remote_script = DaemonProxy(ScriptDefinition(script))

    try:
        assert remote_script.odct == OrderedDict([('a', 1)])
        assert remote_script.foo == "hello world"
    finally:
        remote_script.terminate_daemon()


RESOURCES_DIR = join(__file__, pardir, 'resources')
NOT_IN_PATH_RESOURCES_DIR = join(RESOURCES_DIR, 'not_in_path')


def test_remote_module_from_name():
    """ Simple test with daemon-side instantiation of a io.StringIO """

    # named import
    sys.path.insert(0, RESOURCES_DIR)
    remote_script = DaemonProxy(ModuleDefinition(module_name='dummy'))

    try:
        assert remote_script.odct == OrderedDict([('a', 1)])
        assert remote_script.foo == "hello world"
    finally:
        remote_script.terminate_daemon()


def test_remote_module_from_path():
    """ Simple test with daemon-side instantiation of a io.StringIO """

    # path import
    remote_script = DaemonProxy(ModuleDefinition('dummy2', module_path=join(NOT_IN_PATH_RESOURCES_DIR, 'dummy2.py')))

    try:
        assert remote_script.odct == OrderedDict([('a', 1)])
        assert remote_script.foo == "hello world"
    finally:
        remote_script.terminate_daemon()
