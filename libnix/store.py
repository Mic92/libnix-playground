import ctypes
from ctypes import POINTER, c_void_p, c_char_p, CFUNCTYPE
import asyncio
from dataclasses import dataclass
from typing import Iterator
from contextlib import contextmanager
from pathlib import Path
import os
from concurrent.futures import ThreadPoolExecutor
from .error import NixError
from .pointer import _Pointer
from .loader import _load_library
from .util import nix_err, nix_c_context, LibNixUtil


class Store(ctypes.Structure):
    pass


class StorePath(ctypes.Structure):
    pass


# Define the callback function type
# void (*callback)(void * userdata, const char * outname, const char * out)
StoreRealizeCallback = CFUNCTYPE(None, c_void_p, c_char_p, c_char_p)


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
        POINTER(POINTER(c_char_p)),  # params
    ]
    lib.nix_store_open.restype = POINTER(Store)

    lib.nix_store_free.argtypes = [POINTER(Store)]
    lib.nix_store_free.restype = None

    lib.nix_store_realise.argtypes = [
        POINTER(nix_c_context),  # context
        POINTER(Store),  # store
        POINTER(StorePath),  # path
        c_void_p,  # userdata
        StoreRealizeCallback,  # callback
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
    def _store_path(self, path: str | Path) -> Iterator[_Pointer[StorePath]]:
        store_path = self.libnixstore.lib.nix_store_parse_path(
            self.context, self.store, c_char_p(str(path).encode())
        )
        if not store_path:
            msg = self.libnixutil.nix_err_msg(self.context)
            raise NixError(msg)
        try:
            yield store_path
        finally:
            self.libnixstore.lib.nix_store_path_free(store_path)

    def realise(self, path: str | Path) -> list[BuildOutput]:
        results = []

        @StoreRealizeCallback
        def callback(_userdata: c_void_p, outname: c_char_p, out: c_char_p) -> None:
            assert outname.value is not None, "received null outname in callback"
            assert out.value is not None, "received null out in callback"
            results.append(
                BuildOutput(name=outname.value.decode(), output=out.value.decode())
            )

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

    async def realise(self, path: str | Path) -> list[BuildOutput]:
        loop = asyncio.get_running_loop()

        def realise() -> list[BuildOutput]:
            return self.store.realise(path)

        return await loop.run_in_executor(self.executor, realise)


params_pair = ctypes.c_char_p * 2


def _to_nix_params(params: dict[str, str]) -> _Pointer[_Pointer[c_char_p]]:
    params_list = (POINTER(ctypes.c_char_p) * (len(params) + 1))()
    for i, (key, value) in enumerate(params.items()):
        pair = params_pair(key.encode(), value.encode())
        params_list[i] = ctypes.cast(pair, ctypes.POINTER(ctypes.c_char_p))
    params_list[-1] = None
    return ctypes.cast(params_list, ctypes.POINTER(ctypes.POINTER(ctypes.c_char_p)))


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
        uri: str | Path = "",
        params: dict[str, str] = {},
    ) -> Iterator[AsyncNixStore]:
        with self.open_store(uri, params) as store:
            yield AsyncNixStore(store)

    @contextmanager
    def open_store(
        self,
        uri: str | Path = "",
        params: dict[str, str] = {},
    ) -> Iterator[NixStore]:

        with self.libnixutil.new_nix_c_context() as context:
            store = self.lib.nix_store_open(
                context, str(uri).encode(), _to_nix_params(params)
            )
            if not store:
                msg = self.libnixutil.nix_err_msg(context)
                raise NixError(msg)
            try:
                yield NixStore(store, self, context)
            finally:
                self.lib.nix_store_free(store)
