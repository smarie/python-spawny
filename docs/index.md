# python-object-as-daemon (pyoad)
Tiny utility to spawn an object in a separate process, possibly using another python executable/environment. The object may be accessed from the main process through a proxy with similar behaviour. This project relies on the default multiprocessing module, therefore:

* the child environment does not require any particular package to be present (not even this package). It makes it quite convenient to launch tasks/tests on specific environments.
* communication between processes is done using multiprocessing Pipes

# Installing

```bash
> pip install pyoad
```

# Usage

Let us create a remote StringIO instance and call its `get_value` method.

```python
from pyoad import ObjectDaemonProxy
daemon_strio = ObjectDaemonProxy('io', 'StringIO', 'hello, world!')
print(daemon_strio.getvalue())
```

The outcome is :

```bash
[15756] Object daemon started in : C:\...\python.exe
hello, world!
```

Note that the process id is printed, for reference. You can check in your OS process manager that there is a new python process running under this pid. Now if you dispose of the object by releasing any reference to it, the process automatically terminates:

```python
daemon_strio = None
```

Displays:

```bash
[15756] Object daemon  was asked to exit - closing communication connection
[15756] Object daemon  terminating
```

# See Also

There are many libraries out there that provide much more functionality to distribute objects. The difference with `pyoad` is that they are bigger and typically require something to be installed on the server side. However the gain in features is often incredibly high (distribution over networks, object registries, compliance with other languages...). Check them out ! 

* [PyRo](https://pythonhosted.org/Pyro4/)
* [RPyC](https://rpyc.readthedocs.io/en/latest/)


Some smaller projects from the community:

* [cluster-func](https://pypi.python.org/pypi/cluster-func)
* [dproxify](https://pypi.python.org/pypi/dproxify)


*Do you like this library ? You might also like [these](https://github.com/smarie?utf8=%E2%9C%93&tab=repositories&q=&type=&language=python)* 


## Want to contribute ?

Details on the github page: [https://github.com/smarie/python-object-as-daemon](https://github.com/smarie/python-classtools-autocode) 