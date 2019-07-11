from logging import Logger
from types import MethodType

from spawny.utils_logging import default_logger


def replace_all_dundermethods_with_getattr(ignore,
                                           from_cls,
                                           to_cls_or_inst,
                                           is_class,  # type: bool
                                           logger=default_logger  # type: Logger
                                           ):
    """
    Tool to make `to_cls_or_inst` look like `from_cls` by adding all missing dunder methods. All such created methods
    will redirect all of their calls to `__getattr__`.

    The reason why we have to do this, is because by default python does not redirect "magic" methods to __getattr__.
    All other methods are automatically redirected so there is no need to add them, apart for the user to see them
    in the objects' "dir()". TODO shall we do this ?

    For all methods of `from_cls`, replace or add a method on to_cls_or_inst that relies on __getattr__ to be retrieved.
    If is_class is false, to_cls_or_inst is an instance and only the new methods (not already on the class) will be
    replaced

    :param ignore: a list of names to ignore
    :param from_cls: the original class from which all not ignored dunder methods should be copied
    :param to_cls_or_inst:
    :param is_class:
    :param logger:
    :return:
    """
    def make_proxy(name):
        """Create a method redirecting to __getattr__"""
        def proxy(self, *args):
            return self.__getattr__(name)
        return proxy

    to_replace = [name for name in dir(from_cls) if name.startswith("__") and name not in ignore]
    if is_class:
        logger.debug('Replacing methods ' + str(to_replace) + ' on class ' + to_cls_or_inst.__name__
                     + ' by explicit calls to __getattr__')
    else:
        to_replace = [name for name in to_replace if not hasattr(type(to_cls_or_inst), name)]
        logger.debug('Replacing methods ' + str(to_replace) + ' on instance ' + repr(to_cls_or_inst)
                     + ' by explicit calls to __getattr__')

    for name in to_replace:
        if is_class:
            # that means <name> is not in the ignore list, and not in the explicitly implemented methods (dct)
            # so for those ones, replace the class' method by a proxy redirecting explicitly to getattr
            # logger.debug('Replacing method ' + name + ' on class ' + to_cls_or_inst.__name__)
            setattr(to_cls_or_inst, name, property(make_proxy(name)))
        else:
            # logger.debug('Replacing method ' + name + ' on instance ' + repr(to_cls_or_inst))
            setattr(to_cls_or_inst, name, MethodType(make_proxy(name), to_cls_or_inst))


class ProxifyDunderMeta(type):
    """
    Metaclass to replace all methods in a class, except

     - the ones declared in cls.__ignore__
     - and the ones created explicitly on the class (not inherited)

    with a redirection to __getattr__.
    """
    def __init__(cls, name, bases, dct):
        """
        MetaClass constructor
        :param name:
        :param bases:
        :param dct:
        """
        # as usual
        type.__init__(cls, name, bases, dct)

        # collect all names of methods should not be replaced
        to_ignore = set("__%s__" % n for n in cls.__ignore__.split())
        to_ignore.update(set(dct.keys()))

        # replace all methods with proxies. typically the ones inherited from parent (object)
        replace_all_dundermethods_with_getattr(ignore=to_ignore, from_cls=cls, to_cls_or_inst=cls, is_class=True)

        # add everything from dict class because actually if we do that dynamically (later) that will fail
        # so we should replace ALL magic methods NOW at class creation time
        replace_all_dundermethods_with_getattr(ignore=to_ignore, from_cls=dict, to_cls_or_inst=cls, is_class=True)
        # add the ones from float too for addition, etc.
        replace_all_dundermethods_with_getattr(ignore=to_ignore, from_cls=float, to_cls_or_inst=cls, is_class=True)
