import pytest
import subprocess
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ToyboxDerivation:
    store: Path
    drv_path: Path


@pytest.fixture
def toybox_derivation(
    temporary_directory: Path, toybox: Path, test_root: Path
) -> ToyboxDerivation:
    cmd = subprocess.run(
        [
            "nix-instantiate",
            "--store",
            temporary_directory,
            test_root / "nix" / "toybox-derivation.nix",
            "--arg",
            "toybox",
            toybox,
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    drv_path = Path(cmd.stdout.decode().strip())
    return ToyboxDerivation(temporary_directory, drv_path)
