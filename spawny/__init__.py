from spawny.main_remotes_and_defs import ScriptDefinition, InstanceDefinition, ModuleDefinition
from spawny.main import ObjectDaemonProxy, DaemonProxy, run_script, run_module

# allow user to do
#    import spawny as a
# and then use a.xxx directly (without the intermediate package name)
__all__ = [
    # submodules
    'main',
    # symbols
    'run_script', 'run_module',
    'ObjectDaemonProxy',  # legacy name of DaemonProxy, to remove
    'DaemonProxy', 'InstanceDefinition', 'ScriptDefinition', 'ModuleDefinition'
]
