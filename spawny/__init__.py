from spawny.main_remotes_and_defs import ScriptDefinition, InstanceDefinition, ModuleDefinition
from spawny.main import ObjectProxy, DaemonProxy, run_script, run_module, run_object

# allow user to do
#    import spawny as a
# and then use a.xxx directly (without the intermediate package name)
__all__ = [
    # submodules
    'main',
    # symbols
    'run_script', 'run_module', 'run_object',
    'ObjectProxy', 'DaemonProxy', 'InstanceDefinition', 'ScriptDefinition', 'ModuleDefinition'
]
