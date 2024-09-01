import enum
from ctypes import CDLL, POINTER, c_char_p, Structure, c_uint, c_int

from contextlib import contextmanager
from typing import Iterator

from .loader import _load_library
from .pointer import _Pointer
from .error import NixError


# Define types for the parameters
class nix_c_context(Structure):
    pass


nix_err = c_int


class NixErrorCode(enum.IntEnum):
    NIX_OK = 0
    NIX_ERR_UNKNOWN = -1
    NIX_ERR_OVERFLOW = -2
    NIX_ERR_KEY = -3
    NIX_ERR_NIX_ERROR = -4


def _load_libnixutil() -> CDLL:
    lib = _load_library("nixutilc")
    lib.nix_c_context_create.argtypes = []
    lib.nix_c_context_create.restype = POINTER(nix_c_context)

    lib.nix_c_context_free.argtypes = [POINTER(nix_c_context)]

    lib.nix_libutil_init.argtypes = [POINTER(nix_c_context)]
    lib.nix_libutil_init.restype = nix_err

    lib.nix_err_msg.argtypes = [
        POINTER(nix_c_context),  # context
        POINTER(nix_c_context),  # ctx
        POINTER(c_uint),  # n
    ]
    lib.nix_err_msg.restype = c_char_p

    return lib


class LibNixUtil:
    def __init__(self):
        self.lib = _load_libnixutil()
        with self.new_nix_c_context() as context:
            code = self.lib.nix_libutil_init(context)
            self.check_nix_error(code, context)

    @contextmanager
    def new_nix_c_context(self) -> Iterator[_Pointer[nix_c_context]]:
        context = self.lib.nix_c_context_create()
        if not context:
            raise NixError("Failed to create context")
        try:
            yield context
        finally:
            self.lib.nix_c_context_free(context)

    def check_nix_error(self, code: int, context: _Pointer[nix_c_context]) -> None:
        if code == NixErrorCode.NIX_OK:
            return
        msg = self.nix_err_msg(context)
        raise NixError(msg)

    def nix_err_msg(self, context: _Pointer[nix_c_context]) -> str:
        msg = self.lib.nix_err_msg(None, context, None)
        if not msg:
            return "No error message set"
        return msg.decode()
