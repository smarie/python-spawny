# python-object-as-daemon (pyoad)
Tiny utility to spawn an object in a separate process, possibly using another python executable/environment. The object may be accessed from the main process through a proxy with similar behaviour. This project relies on the default multiprocessing module, therefore:

* the child environment does not require any particular package to be present (not even this package). It makes it quite convenient to launch tasks/tests on specific environments.
* communication between processes is done using multiprocessing Pipes

## Installing

```bash
> pip install pyoad
```

## Basic Usage

### Creating

Let us create a string instance and send it into a daemon:

```python
from pyoad import ObjectDaemonProxy
daemon_str = ObjectDaemonProxy('hello, world!')
```

The outcome is :

```bash
[15756] Object daemon started in : C:\Anaconda3\envs\tools\python.exe
```

Note that the spawned process id is printed, for reference (here, `[15756]`). You can check in your OS process manager that there is a new python process running under this pid.


### Calling
 
You may now interact with the proxy as if the object were still local:

```python
print(daemon_str)
print(daemon_str[0:5])
```

```bash
hello, world!
hello
```

### Disposing

If you dispose of the object by releasing any reference to it, the daemon process will automatically terminate the next time the python garbage collector runs:

```python
daemon_str = None
import gc
gc.collect()  # explicitly ask for garbage collection right now
```

Displays:

```bash
[15756] Object daemon  was asked to exit - closing communication connection
[15756] Object daemon  terminating
```

## Advanced

### Daemon-side instantiation

In most cases you'll probably want the daemon to instantiate the object, not the main process. For this purpose the `InstanceDefinition` class may be used to describe what you want to instantiate:

```python
from pyoad import ObjectDaemonProxy, InstanceDefinition
definition = InstanceDefinition('io', 'StringIO', 'hello, world!')
daemon_strio = ObjectDaemonProxy(definition)
print(daemon_strio.getvalue())
```

Note that the module name may be set to `builtins` for built-ins:

```python
from pyoad import ObjectDaemonProxy, InstanceDefinition
daemon_str_int = ObjectDaemonProxy(InstanceDefinition('builtins', 'str', 1))
print(daemon_str_int)
```

Note: if the module is set to `None`, the class name is looked for in `globals()`

### Choice of python executable/environment

You may wish to run the daemon in a given python environment, typically different from the one your main process runs into:

```python
daemon = ObjectDaemonProxy(..., python_exe='<path_to_python.exe>')
```


### Log levels

This is how you change the module default logging level : 

```python
import logging
logging.getLogger('pyoad').setLevel(logging.DEBUG)
```

Otherwise you may also wish to provide your own logger:

```python
daemon = ObjectDaemonProxy(..., logger = MyLogger())
```


## See Also

There are many libraries out there that provide much more functionality to distribute objects. The difference with `pyoad` is that they are bigger and typically require something to be installed on the server side. However the gain in features is often incredibly high (distribution over networks, object registries, compliance with other languages...). Check them out ! 

* [PyRo](https://pythonhosted.org/Pyro4/)
* [RPyC](https://rpyc.readthedocs.io/en/latest/)


Some smaller projects from the community:

* [cluster-func](https://pypi.python.org/pypi/cluster-func)
* [dproxify](https://pypi.python.org/pypi/dproxify)


*Do you like this library ? You might also like [these](https://github.com/smarie?utf8=%E2%9C%93&tab=repositories&q=&type=&language=python)* 

## Want to contribute ?

Details on the github page: [https://github.com/smarie/python-object-as-daemon](https://github.com/smarie/python-classtools-autocode) 