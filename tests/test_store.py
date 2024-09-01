import asyncio
import pytest

from libnix.store import LibNixStore

from toybox_derivation import ToyboxDerivation


@pytest.mark.asyncio
async def test_async_store(
    toybox_derivation: ToyboxDerivation, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("NIX_REMOTE", raising=False)
    with LibNixStore().open_async_store(
        toybox_derivation.store, dict(state=str(toybox_derivation.store))
    ) as store:
        await asyncio.gather(
            store.realise(toybox_derivation.drv_path),
            store.realise(toybox_derivation.drv_path),
            store.realise(toybox_derivation.drv_path),
        )


def test_sync_store(
    toybox_derivation: ToyboxDerivation, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("NIX_REMOTE", raising=False)
    with LibNixStore().open_store(
        toybox_derivation.store, dict(state=str(toybox_derivation.store))
    ) as store:
        store.realise(toybox_derivation.drv_path)
