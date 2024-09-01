import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def temporary_directory() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="pytest-") as dirpath:
        yield Path(dirpath)
