# allow users to do
#     from pyoad import xxx
from pyoad.main import *

# allow user to do
#    import pyoad as a
# and then use a.xxx directly (without the intermediate package name)
__all__ = ['main']
