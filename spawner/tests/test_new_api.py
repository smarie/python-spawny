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
    remote_odct = remote_script.odct

    print(remote_odct)
