from ctypes import _Pointer, POINTER
from typing import TYPE_CHECKING

if not TYPE_CHECKING:
    class pointer_fix:
        @classmethod
        def __class_getitem__(cls, item):
            return POINTER(item)

    _Pointer = pointer_fix
