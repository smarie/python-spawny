# spawny

*Spawn python code in a separate python interpreter and communicate with it easily.*

[![Python versions](https://img.shields.io/pypi/pyversions/getversion.svg)](https://pypi.python.org/pypi/getversion/) [![Build Status](https://travis-ci.org/smarie/python-spawny.svg?branch=master)](https://travis-ci.org/smarie/python-spawny) [![Tests Status](https://smarie.github.io/python-spawny/junit/junit-badge.svg?dummy=8484744)](https://smarie.github.io/python-spawny/junit/report.html) [![codecov](https://codecov.io/gh/smarie/python-spawny/branch/master/graph/badge.svg)](https://codecov.io/gh/smarie/python-spawny)

[![Documentation](https://img.shields.io/badge/doc-latest-blue.svg)](https://smarie.github.io/python-spawny/) [![PyPI](https://img.shields.io/pypi/v/spawny.svg)](https://pypi.python.org/pypi/spawny/) [![Downloads](https://pepy.tech/badge/spawny)](https://pepy.tech/project/spawny) [![Downloads per week](https://pepy.tech/badge/spawny/week)](https://pepy.tech/project/spawny) [![GitHub stars](https://img.shields.io/github/stars/smarie/python-spawny.svg)](https://github.com/smarie/python-spawny/stargazers)

!!! success "New: entire scripts can now be run remotely, [check it out](#executing-a-script) !"

Do you want to run python code in a separate process, in a separate python interpreter, while still being able to communicate with it easily ? `spawny` was made for this. 

It relies on the built-in [`multiprocessing`](https://docs.python.org/3/library/multiprocessing.html#module-multiprocessing) module, but provides a higher-level API so that it is **extremely easy for a non-expert** to get started. The child python environment does not require any particular package to be present (not even the `spawny` package). The subprocess may be accessed from the main process through a **"proxy" python object**. Simply call that object, this will use a multiprocessing `Pipe` behind the scenes.

## Installing

```bash
> pip install spawny
```

## Usage

### Executing a script

Let's write some python code and put it in a variable:

```python
script = """
from collections import OrderedDict

odct = OrderedDict()
odct['a'] = 1

foo = "hello world"

def say_hello(who):
    return "hello %s" % who

print(say_hello("process"))    
"""
```

To execute this script in a subprocess, all you have to do is call `run_script`:

```python
from spawny import run_script

# execute the script in another process
daemon_module = run_script(script)
```

It yields:

```bash
[DaemonProxy] spawning child process...
[11100] Daemon started using python interpreter: <path>/python.exe
hello, process!
[DaemonProxy] spawning child process... DONE. PID=11100
```

Now your script is running in a subprocess, with process id `11100` as indicated in the printed message.  You can check in your OS process manager that there is a new python process running under this pid. What happened behind the scenes is that the subprocess spawned loaded your script in a dynamically created module. You can see that module was ent with the `hello, process!` print that comes from the end of the script.


The `daemon_module` variable now contains a proxy able to communicate with it through inter-process communication (`multiprocessing.Pipe`). So you can access all the variables created in your script, and each variable will contain a proxy to the respective object. You can interact with each variable as it the objects were here:

```python
# interact with it:
print(daemon_module.odct)
assert daemon_module.foo == "hello world"
assert daemon_module.say_hello("earthling") == "hello earthling"
```

Note that the results of interacting with these variables are then received as plain python object, not as proxy. Only the main variable (`daemon_module`) and the first-level variables (`daemon_module.odct`, etc.) are proxies. You can check it with:

```python
print(type(daemon_module.foo))                     # ObjectProxy
print(type(daemon_module.say_hello("earthling")))  # str
```

### Disposing

If you dispose of the object by releasing any reference to it, the daemon process will automatically terminate the next time the python garbage collector runs:

```python
daemon_module = None
import gc
gc.collect()  # explicitly ask for garbage collection right now
```

Displays:

```bash
[11100] Object daemon  was asked to exit - closing communication connection
[11100] Object daemon  terminating
```

Note that this only happens if there is no remaining object proxy in any of your variable.
You can reach the same result explicitly, by calling the `.terminate_daemon()` method on any of your object proxies (the main one or the second-level ones):

```python
daemon_module.terminate_daemon()
```

### Executing a module

Simply use `run_module` instead of `run_script`. You can either provide a module name if the module is already imported, or a name and a path if the module file is not imported in the caller process.

### Executing a single object

For this purpose the `InstanceDefinition` class may be used to describe what you want to instantiate:

```python
from spawny import InstanceDefinition, run_object
definition = InstanceDefinition('io', 'StringIO', 'hello, world!')
daemon_strio = run_object(definition)
print(daemon_strio.getvalue())
```

Note that the module name may be set to `builtins` for built-ins:

```python
from spawny import run_object, InstanceDefinition
daemon_str_int = run_object(InstanceDefinition('builtins', 'str', 1))
print(daemon_str_int)
```

Note: if the module is set to `None`, the class name is looked for in `globals()`

## Advanced

### Choice of python executable/environment

You may wish to run the daemon in a given python environment, typically different from the one your main process runs into:

```python
daemon = run_xxx(..., python_exe='<path_to_python.exe>')
```


### Log levels

This is how you change the module default logging level : 

```python
import logging
logging.getLogger(spawny).setLevel(logging.DEBUG)
```

Otherwise you may also wish to provide your own logger:

```python
from logging import getLogger, FileHandler, INFO
my_logger = getLogger('mine')
my_logger.addHandler(FileHandler('hello.log'))
my_logger.setLevel(INFO)
daemon = run_xxx(..., logger = my_logger)
```


## See Also

 * The [`multiprocessing`](https://docs.python.org/3/library/multiprocessing.html#module-multiprocessing) built-in python module.


There are many libraries out there that provide much more functionality to distribute objects. The difference with `spawny` is that they are bigger and typically require something to be installed on the server side. However the gain in features is often incredibly high (distribution over networks, object registries, compliance with other languages...). Check them out ! 

 * [PyRo](https://pythonhosted.org/Pyro4/)
 * [RPyC](https://rpyc.readthedocs.io/en/latest/)


Some smaller projects from the community:

 * [cluster-func](https://pypi.python.org/pypi/cluster-func)
 * [dproxify](https://pypi.python.org/pypi/dproxify)


*Do you like this library ? You might also like [my other python libraries](https://github.com/smarie?utf8=%E2%9C%93&tab=repositories&q=&type=&language=python)* 

## Want to contribute ?

Details on the github page: [https://github.com/smarie/python-spawny](https://github.com/smarie/python-classtools-autocode) 