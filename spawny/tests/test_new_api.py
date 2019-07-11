import sys
from collections import OrderedDict
from os.path import join, dirname
from pickle import PicklingError

import pytest

from spawny import run_script, run_module, ObjectProxy


PY2 = sys.version_info < (3, 0)


def test_remote_script():
    """ Simple test with a script provided as string """

    script = """
from collections import OrderedDict

odct = OrderedDict()
odct['a'] = 1

foo = "hello world"
"""

    remote_script = run_script(script)
    assert isinstance(remote_script, ObjectProxy)

    try:
        assert isinstance(remote_script.odct, ObjectProxy)
        assert remote_script.odct == OrderedDict([('a', 1)])

        assert isinstance(remote_script.foo, ObjectProxy)
        assert remote_script.foo == "hello world"
    finally:
        remote_script.terminate_daemon()


RESOURCES_DIR = join(dirname(__file__), 'resources')
NOT_IN_PATH_RESOURCES_DIR = join(RESOURCES_DIR, 'not_in_path')


@pytest.mark.parametrize("module_in_syspath", [True, False], ids="module_in_syspath={}".format)
def test_remote_module_from_name(module_in_syspath):
    """ Simple test with daemon-side instantiation of a io.StringIO """

    # spawn
    if module_in_syspath:
        sys.path.insert(0, RESOURCES_DIR)
        remote_script = run_module(module_name='dummy')
    else:
        remote_script = run_module(module_name='dummy', module_path=join(RESOURCES_DIR, 'dummy.py'))

    # the result is a proxy for the module
    assert isinstance(remote_script, ObjectProxy)

    try:
        remote_i_proxy = remote_script.i
        assert isinstance(remote_i_proxy, ObjectProxy)
        assert remote_i_proxy == 1
        # remote addition !
        assert remote_i_proxy + 1 == 2
        # remote addition AND set !
        remote_i_proxy += 1
        assert remote_i_proxy == 2

        assert isinstance(remote_script.odct, ObjectProxy)
        assert remote_script.odct == OrderedDict([('a', 1)])

        assert isinstance(remote_script.foo_str, ObjectProxy)
        assert remote_script.foo_str == "hello world"

        # assert isinstance(remote_script.say_hello, ObjectProxy) -> not an ObjectProxy, a method proxy
        assert remote_script.say_hello("earthling") == "hello, earthling!"

        assert isinstance(remote_script.foo, ObjectProxy)
        assert isinstance(remote_script.Foo, ObjectProxy)
        assert remote_script.foo.say_hello('mister') == '[Foo-1] hello, mister!'

        if module_in_syspath or PY2:  # TODO why does it work on python 2 ?!!!
            assert remote_script.Foo(1) == remote_script.foo
        else:
            with pytest.raises(PicklingError):
                remote_script.Foo(1)

    finally:
        if module_in_syspath:
            sys.path.pop(0)
        remote_script.terminate_daemon()
