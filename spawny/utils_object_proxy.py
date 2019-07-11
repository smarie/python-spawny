from logging import Logger
from types import MethodType

from spawny.utils_logging import default_logger


def replace_all_dundermethods_with_getattr(ignore,
                                           from_cls,
                                           to_cls_or_inst,
                                           is_class,                # type: bool
                                           logger = default_logger  # type: Logger
                                           ):
    """
    For all methods of from_cls replace/add a method on to_cls_or_inst that relies on __getattr__ to be retrieved.
    If is_class is false, to_cls_or_inst is an instance and only the new methods (not already on the class) will be
    replaced

    :param ignore:
    :param from_cls:
    :param to_cls_or_inst:
    :param is_class:
    :param logger:
    :return:
    """
    def make_proxy(name):
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
    def __init__(cls, name, bases, dct):
        type.__init__(cls, name, bases, dct)
        to_ignore = set("__%s__" % n for n in cls.__ignore__.split())
        to_ignore.update(set(dct.keys()))
        replace_all_dundermethods_with_getattr(to_ignore, cls, cls, is_class=True)
        # add everything from dict class so that at least
        replace_all_dundermethods_with_getattr(to_ignore, dict, cls, is_class=True)
