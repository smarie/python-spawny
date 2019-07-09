from collections import OrderedDict

from spawner import ScriptDefinition, DaemonProxy


def test_mini_instance_def():
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
