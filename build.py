import ctypes
from ctypes import POINTER, c_void_p, c_char_p, CFUNCTYPE, _Pointer
import enum
import sys
import asyncio
from dataclasses import dataclass
from typing import Iterator, TYPE_CHECKING
from contextlib import contextmanager
from pathlib import Path
import os
import sysconfig
from concurrent.futures import ThreadPoolExecutor

if not TYPE_CHECKING:

    class pointer_fix:
        @classmethod
        def __class_getitem__(cls, item):
            return POINTER(item)

    _Pointer = pointer_fix


class NixErrorCode(enum.IntEnum):
    NIX_OK = 0
    NIX_ERR_UNKNOWN = -1
    NIX_ERR_OVERFLOW = -2
    NIX_ERR_KEY = -3
    NIX_ERR_NIX_ERROR = -4


class NixError(Exception):
    pass


# Define types for the parameters
class nix_c_context(ctypes.Structure):
    pass


class Store(ctypes.Structure):
    pass


class StorePath(ctypes.Structure):
    pass


NixCContext = POINTER(nix_c_context)
nix_err = ctypes.c_int


# Define the callback function type
# void (*callback)(void * userdata, const char * outname, const char * out)
CallbackType = CFUNCTYPE(None, c_void_p, c_char_p, c_char_p)

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


def _load_libnixutil() -> ctypes.CDLL:
    lib = _load_library("nixutilc")
    lib.nix_c_context_create.argtypes = []
    lib.nix_c_context_create.restype = POINTER(nix_c_context)

    lib.nix_c_context_free.argtypes = [POINTER(nix_c_context)]

    lib.nix_libutil_init.argtypes = [POINTER(nix_c_context)]
    lib.nix_libutil_init.restype = nix_err

    lib.nix_err_msg.argtypes = [
        POINTER(nix_c_context),  # context
        POINTER(nix_c_context),  # ctx
        POINTER(ctypes.c_uint),  # n
    ]
    lib.nix_err_msg.restype = c_char_p

    return lib


def _load_libnixstore() -> ctypes.CDLL:
    lib = _load_library("nixstorec")

    lib.nix_libstore_init.argtypes = [
        POINTER(nix_c_context)  # context
    ]
    lib.nix_libstore_init.restype = nix_err

    # Store * nix_store_open(nix_c_context * context, const char * uri, const char *** params);
    lib.nix_store_open.argtypes = [
        POINTER(nix_c_context),  # context
        c_char_p,  # uri
        POINTER(c_char_p),  # params
    ]
    lib.nix_store_open.restype = POINTER(Store)

    lib.nix_store_free.argtypes = [POINTER(Store)]
    lib.nix_store_free.restype = None

    lib.nix_store_realise.argtypes = [
        POINTER(nix_c_context),  # context
        POINTER(Store),  # store
        POINTER(StorePath),  # path
        c_void_p,  # userdata
        CallbackType,  # callback
    ]
    lib.nix_store_realise.restype = nix_err

    lib.nix_store_parse_path.argtypes = [
        POINTER(nix_c_context),  # context
        POINTER(Store),  # store
        c_char_p,  # path
    ]
    lib.nix_store_parse_path.restype = POINTER(StorePath)

    lib.nix_store_path_free.argtypes = [POINTER(StorePath)]
    lib.nix_store_path_free.restype = None

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


@dataclass
class BuildOutput:
    name: str
    output: str


class NixStore:
    def __init__(
        self,
        store: _Pointer[Store],
        libnixstore: "LibNixStore",
        context: _Pointer[nix_c_context],
    ):
        self.store = store
        self.libnixstore = libnixstore
        self.libnixutil = libnixstore.libnixutil
        self.context = context

    @contextmanager
    def _store_path(self, path: str) -> Iterator[_Pointer[StorePath]]:
        store_path = self.libnixstore.lib.nix_store_parse_path(
            self.context, self.store, c_char_p(path.encode())
        )
        if not store_path:
            msg = self.libnixutil.nix_err_msg(self.context)
            raise NixError(msg)
        try:
            yield store_path
        finally:
            self.libnixstore.lib.nix_store_path_free(store_path)

    def realise(self, path: str) -> list[BuildOutput]:
        results = []

        @CallbackType
        def callback(userdata: c_void_p, outname: c_char_p, out: c_char_p) -> None:
            results.append(BuildOutput(name=outname.decode(), output=out.decode()))

        with self._store_path(path) as store_path:
            err = self.libnixstore.lib.nix_store_realise(
                self.context, self.store, store_path, None, callback
            )
        self.libnixutil.check_nix_error(err, self.context)
        return results


class AsyncNixStore:
    def __init__(self, store: NixStore):
        self.store = store
        self.executor = ThreadPoolExecutor(min(os.cpu_count() or 10, 10))

    async def realise(self, path: str) -> list[BuildOutput]:
        loop = asyncio.get_running_loop()

        def realise() -> list[BuildOutput]:
            return self.store.realise(path)

        return await loop.run_in_executor(self.executor, realise)


class LibNixStore:
    def __init__(
        self,
        libnixutil: LibNixUtil | None = None,
    ):
        self.lib = _load_libnixstore()
        if not libnixutil:
            libnixutil = LibNixUtil()
        self.libnixutil = libnixutil
        with self.libnixutil.new_nix_c_context() as context:
            code = self.lib.nix_libstore_init(context)
            self.libnixutil.check_nix_error(code, context)

    @contextmanager
    def open_async_store(
        self,
        uri: str="",
        params: _Pointer[c_char_p] = POINTER(c_char_p)(),
    ) -> Iterator[AsyncNixStore]:
        with self.open_store(uri, params) as store:
            yield AsyncNixStore(store)

    @contextmanager
    def open_store(
        self,
        uri: str="",
        params: _Pointer[c_char_p] = POINTER(c_char_p)(),
    ) -> Iterator[NixStore]:
        with self.libnixutil.new_nix_c_context() as context:
            store = self.lib.nix_store_open(context, uri.encode(), params)
            if not store:
                msg = self.libnixutil.nix_err_msg(context)
                raise NixError(msg)
            try:
                yield NixStore(store, self, context)
            finally:
                self.lib.nix_store_free(store)


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: build.py drv", file=sys.stderr)
        sys.exit(1)
    drv = sys.argv[1]
    try:
        # async
        libnixstore = LibNixStore()
        with libnixstore.open_async_store() as store:
            await asyncio.gather(
                store.realise(drv),
                store.realise(drv),
                store.realise(drv),
            )
        # sync
        with libnixstore.open_store() as store:
            store.realise(drv)
    except NixError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    asyncio.run(main())
