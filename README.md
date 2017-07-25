# python-object-as-daemon (pyoad)

Project page : [https://smarie.github.io/python-object-as-daemon/](https://smarie.github.io/python-object-as-daemon/)

## What's new

* Doc now generated from markdown using [mkdocs](http://www.mkdocs.org/)
* most special methods are now correctly proxified
* object instance can now be created on either side (main process or daemon)

## Want to contribute ?

Contributions are welcome ! Simply fork this project on github, commit your contributions, and create pull requests.

Here is a non-exhaustive list of interesting open topics: [https://github.com/smarie/python-object-as-daemon/issues](https://github.com/smarie/python-object-as-daemon/issues)

## Packaging

This project uses `setuptools_scm` to synchronise the version number. Therefore the following command should be used for development snapshots as well as official releases: 

```bash
python setup.py egg_info bdist_wheel rotate -m.whl -k3
```

### Releasing memo

```bash
twine upload dist/* -r pypitest
twine upload dist/*
```
