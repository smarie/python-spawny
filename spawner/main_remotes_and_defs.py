from imp import new_module
from importlib import import_module

try:  # python 3.5+
    from typing import Optional
except ImportError:
    pass


class InstanceDefinition(object):
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


class ScriptDefinition(object):
    """
    Represents a script to run remotely
    """
    __slots__ = 'script',

    def __init__(self, script_as_str):
        self.script = script_as_str

    def execute(self):
        """
        Creates a new module and executes the script in it. The newly created module is returned.
        :return:
        """
        # find a suitable name
        name = '<spawner-remote-module-%s>'
        i = 0
        while (name % i) in globals():
            i += 1

        # create a new module with that name, and execute the script in it
        m = new_module(name % i)
        exec(self.script, m.__dict__)
        return m
