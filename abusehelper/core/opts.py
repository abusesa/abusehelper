import os
import sys
import inspect
from optparse import OptionParser
from ConfigParser import SafeConfigParser

def long_name(key):
    return key.replace("_", "-").lower()

def action_and_type(default):
    if isinstance(default, bool):
        if default:
            return "store_false", None
        return "store_true", None
    elif isinstance(default, int):
        return "store", "int"
    elif isinstance(default, float):
        return "store", "float"
    return "store", "string"

def optparse(func, argv=list(sys.argv[1:])):
    args, varargs, varkw, defaults = inspect.getargspec(func)

    assert varargs is None, "variable argument definitions are not supported"
    assert varkw is None, "variable keyword definitions are not supported"

    if not defaults:
        positionals = args
        defaults = dict()
    else:
        positionals = args[:-len(defaults)]
        defaults = dict(zip(args[-len(defaults):], defaults))

    parser = OptionParser()
    usage = list()
    usage.append("Usage: %prog [options]")
    for name in positionals:
        usage.append(name)
    parser.set_usage(" ".join(usage))

    # Add the INI config file parsing options. The INI section name is
    # magically determined from the given function's module file name
    # (e.g. filename '../lib/testmodule.py' -> section 'testmodule').
    parser.add_option("--ini-file", 
                      dest="ini_file", 
                      default=None,
                      help="INI file used for configuration", 
                      metavar="ini_file")
    _, module_file = os.path.split(inspect.getmodule(func).__file__)
    section_name, _ = os.path.splitext(module_file)
    parser.add_option("--ini-section", 
                      dest="ini_section", 
                      default=section_name,
                      help=("if an INI configuration file is specified, "+
                            "use this section (default: %default)"),
                      metavar="ini_section")

    long_names = dict()
    for key in args:
        long = getattr(func, key + "_long", long_name(key))
        long_names[key] = long
        short = getattr(func, key + "_short", None)
        
        names = list()
        if short is not None:
            names.append("-" + short)
        names.append("--" + long)

        kwargs = dict()
        kwargs["dest"] = key
        kwargs["help"] = getattr(func, key + "_help", None)
        kwargs["metavar"] = getattr(func, key + "_metavar", key)

        if key in defaults:
            default = defaults[key]
            action, type = action_and_type(default)
            kwargs["default"] = default
            kwargs["action"] = getattr(func, key + "_action", action)
            kwargs["type"] = getattr(func, key + "_type", type)

        option = parser.add_option(*names, **kwargs)

    options, params = parser.parse_args(list(argv))

    # Open and parse the INI configuration file, if given.
    if options.ini_file is not None:
        config = SafeConfigParser()
        config.read([options.ini_file])

        section_name = options.ini_section
        if config.has_section(section_name):
            section = dict(config.items(section_name))
        else:
            section = config.defaults()

        argv = list(argv)
        for key in args:
            if key in section:
                argv.insert(0, "--%s=%s" % (long_names[key], section[key]))
        options, params = parser.parse_args(argv)

    arglist = list()
    for key in args:
        positional = key in positionals
        if not positional or getattr(options, key) is not None:
            arglist.append(getattr(options, key))
        elif positional and params:
            arglist.append(params.pop(0))
        else:
            parser.error("missing value for argument %s" % key)            
    if params:
        parser.error("too many positional arguments")        

    return func(*arglist)
