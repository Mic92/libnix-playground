from tempfile import TemporaryDirectory
import pytest
import shutil
from pathlib import Path
from typing import Iterator
from dataclasses import dataclass


@pytest.fixture(scope="session")
def toybox() -> Path:
    with TemporaryDirectory() as store:
        toybox = shutil.which("toybox")
        if not toybox:
            raise RuntimeError("toybox not found")
        return Path(toybox)
