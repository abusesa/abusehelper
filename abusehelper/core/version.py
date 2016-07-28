from .. import __version__


import warnings
warnings.warn(
    "Module abusehelper.core.version has been deprecated. Please use abusehelper.__version__ instead.",
    DeprecationWarning
)


def version():
    return __version__


def version_str():
    return __version__


if __name__ == "__main__":
    print __version__
