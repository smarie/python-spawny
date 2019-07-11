from abc import ABCMeta, abstractmethod
from imp import new_module
from importlib import import_module
from types import ModuleType

from six import with_metaclass

try:  # python 3.5+
    from typing import Optional
except ImportError:
    pass

try: # python 3.5+
    from importlib import util as import_util

    def import_from_source(module_name, module_path):
        spec = import_util.spec_from_file_location(module_name, module_path)
        foo = import_util.module_from_spec(spec)
        spec.loader.exec_module(foo)
        return foo

except ImportError:
    # python 2
    import imp

    def import_from_source(module_name, module_path):
        foo = imp.load_source(module_name, module_path)
        return foo


class Definition(with_metaclass(ABCMeta, object)):
    @abstractmethod
    def get_type(self):
        pass

    @abstractmethod
    def is_multi_object(self):
        pass


class InstanceDefinition(Definition):
    """
    Represents the definition of an object instance to create.
    """

    def __init__(self,
                 module_name,  # type: Optional[str]
                 clazz_name,   # type: str
                 *args,
                 **kwargs
                 ):
        """
        Creates a definition to instantiate an object of class `clazz_name` in module `module_name`, with constructor
        arguments *args and **kwargs. Submodules are supported, simply add them in `module_name` with the dot notation,
        such as 'os.path'. To create instances of build-in types such as 'int', set module_name to '' or None.

        :param module_name:
        :param clazz_name:
        :param args:
        :param kwargs:
        """
        self.module_name = module_name
        self.clazz_name = clazz_name
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return ('' if self.module_name is None else self.module_name) + '.' + self.clazz_name + '(' + str(self.args) \
               + ';' + str(self.kwargs) + ')'

    def get_type(self):
        """
        Utility method to return the class of objects corresponding to this definition
        :return:
        """
        # find the class, optionally from an imported module
        if self.module_name is not None and self.module_name != '':
            m = import_module(self.module_name)
            clazz = getattr(m, self.clazz_name)
        else:
            clazz = globals()[self.clazz_name]
        return clazz

    def instantiate(self):
        """
        Utility method to instantiate an object corresponding to this definition
        :return:
        """
        # find the class
        clazz = self.get_type()

        # instantiate
        return clazz(*self.args, **self.kwargs)

    def is_multi_object(self):
        return False


class ScriptDefinition(Definition):
    """
    Represents a script to run remotely
    """
    __slots__ = 'script',

    def __init__(self,
                 script_as_str  # type: str
                 ):
        self.script = script_as_str

    def execute(self):
        """
        Creates a new module and executes the script in it. The newly created module is returned.
        :return:
        """
        # find a suitable name
        name = '<spawny-remote-module-%s>'
        i = 0
        while (name % i) in globals():
            i += 1

        # create a new module with that name, and execute the script in it
        m = new_module(name % i)
        exec(self.script, m.__dict__)
        # return RemoteScript(m)
        return m

    def get_type(self):
        return ModuleType

    def is_multi_object(self):
        return True

# class RemoteScript(object):
#     __slots__ = 'module',
#
#     def __init__(self, module):
#         self.module = module
#
#     def __getattr__(self, item):
#         if item == 'module':
#             return object.__getattribute__(self, item)
#         else:
#             return self.module.item
#
#     def __setattr__(self, item, value):
#         if item == 'module':
#             object.__setattr__(self, item, value)
#         else:
#             self.module.item = value


class ModuleDefinition(Definition):
    """
    Represents a module to run remotely
    """
    __slots__ = 'module_name', 'module_path'

    def __init__(self,
                 module_name,
                 module_path=None
                 ):
        """

        :param module_name:
        :param module_path:
        """
        self.module_name = module_name
        self.module_path = module_path

    def execute(self):
        """
        Creates a new module and executes the script in it. The newly created module is returned.
        :return:
        """
        if self.module_path is None:
            m = import_module(self.module_name)
        else:
            m = import_from_source(self.module_name, self.module_path)
        return m

    def get_type(self):
        return ModuleType

    def is_multi_object(self):
        return True
