import os
import sysconfig
import ctypes
from pathlib import Path
from .error import NixError

LIBNIX_PATH = os.environ.get("LIBNIX_PATH", "@libnix_path@")

def _load_library(name: str) -> ctypes.CDLL:
    if LIBNIX_PATH == "@libnix_path@":
        raise NixError("LIBNIX_PATH not set")
    libext = sysconfig.get_config_var("SHLIB_SUFFIX")
    lib = Path(LIBNIX_PATH) / f"lib{name}{libext}"
    if not lib.exists():
        msg = f"lib{name} not found"
        raise NixError(msg)
    return ctypes.CDLL(str(lib))

