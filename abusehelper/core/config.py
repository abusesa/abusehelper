import os
import sys
import imp
import inspect
import compiler

def base_dir(depth=1):
    calling_frame = inspect.stack()[depth]
    calling_file = calling_frame[1]
    return os.path.dirname(os.path.abspath(calling_file))

def relative_path(*path):
    return os.path.abspath(os.path.join(base_dir(depth=2), *path))

def load_module(module_name, relative_to_caller=True):
    base = base_dir(depth=2)

    path, name = os.path.split(module_name)
    if not path:
        if relative_to_caller:
            paths = [base]
        else:
            paths = None
        found = imp.find_module(name, paths)
        sys.modules.pop(name, None)
        return imp.load_module(name, *found)

    if relative_to_caller:
        module_name = os.path.join(base, module_name)

    module_file = open(module_name, "r")
    try:
        source = module_file.read()
    finally:
        module_file.close()

    code = compiler.compile(source, module_name, "exec")

    local_namespace = dict()
    global_namespace = dict()
    exec code in global_namespace, local_namespace
    global_namespace.update(local_namespace)

    module = imp.new_module(module_name)
    for key, value in local_namespace.iteritems():
        setattr(module, key, value)
    return module

def flatten(obj):
    """
    >>> list(flatten([1, 2]))
    [1, 2]
    >>> list(flatten([[1, [2, 3]], 4]))
    [1, 2, 3, 4]

    >>> list(flatten([xrange(1, 3), xrange(3, 5)]))
    [1, 2, 3, 4]

    >>> list(flatten(list))
    []
    """

    if callable(obj):
        for flattened in flatten(obj()):
            yield flattened
        return

    try:
        iterable = iter(obj)
    except TypeError:
        yield obj
        return

    for item in iterable:
        for flattened in flatten(item):
            yield flattened

def load_configs(module_name, config_name="configs"):
    module = load_module(module_name, False)
    if not hasattr(module, config_name):
        raise ImportError("no %r defined in module %r" %
                          (config_name, module.__name__))

    config_attr = getattr(module, config_name)
    return flatten(config_attr)
