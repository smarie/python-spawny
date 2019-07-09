from spawner.main_remotes_and_defs import ScriptDefinition, InstanceDefinition
from spawner.main import ObjectDaemonProxy, DaemonProxy

# allow user to do
#    import spawner as a
# and then use a.xxx directly (without the intermediate package name)
__all__ = [
    # submodules
    'main',
    # symbols
    'ObjectDaemonProxy',  # legacy name of DaemonProxy, to remove
    'DaemonProxy', 'InstanceDefinition', 'ScriptDefinition'
]
