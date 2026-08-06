from __future__ import annotations

import dataclasses
import pickle
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

type ID = str

try:
    import polars as pl

    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False


class Store(ABC):
    @abstractmethod
    def exists(self, asset: Asset) -> bool:
        pass

    @abstractmethod
    def read(self, asset: Asset):
        pass

    @abstractmethod
    def write(self, asset: Asset, obj):
        pass


class MemoryStore(Store):
    def __init__(self):
        self.assets: dict[ID, Asset] = {}

    def exists(self, asset: Asset) -> bool:
        return asset.id in self.assets

    def read(self, asset: Asset):
        return self.assets[asset.id]

    def write(self, asset: Asset, obj):
        self.assets[asset.id] = obj


class FileStore(Store, ABC):
    def __init__(self, dir: str | Path):
        self.dir = Path(dir)
        assert self.dir.is_dir()

    @abstractmethod
    def artifact_path(self, asset: Asset) -> Path:
        raise NotImplementedError()

    def exists(self, asset: Asset) -> bool:
        return self.artifact_path(asset).exists()

    def pickle_store(self) -> PickleStore:
        return PickleStore(dir=self.dir)

    def parquet_store(self) -> ParquetStore:
        return ParquetStore(dir=self.dir)


class PickleStore(FileStore):
    def artifact_path(self, asset: Asset) -> Path:
        return self.dir / f"{asset.id}.pkl"

    def read(self, asset: Asset):
        path = self.artifact_path(asset)
        with open(path, "rb") as f:
            return pickle.load(f)

    def write(self, asset: Asset, obj):
        path = self.artifact_path(asset)
        with open(path, "wb") as f:
            pickle.dump(obj, f)


class ParquetStore(FileStore):
    def __post_init__(self):
        if not HAS_POLARS:
            raise ImportError("fiat[polars] is required for ParquetStore")

    def artifact_path(self, asset: Asset) -> Path:
        return self.dir / f"{asset.id}.parquet"

    def read(self, asset: Asset) -> pl.DataFrame:
        path = self.artifact_path(asset)
        return pl.read_parquet(path)

    def write(self, asset: Asset, obj: pl.DataFrame):
        if not isinstance(obj, pl.DataFrame):
            raise ValueError(
                f"Cannot write '{obj}' of type {type(obj)} to parquet store"
            )
        path = self.artifact_path(asset)
        obj.write_parquet(path)


class Catalog:
    def __init__(self):
        self.assets: list[Asset] = []

    def register(self, store: Store, fun: Callable, id: ID, deps: list[ID]):
        self.assets.append(Asset(catalog=self, store=store, id=id, fun=fun, deps=deps))

    def materialize(self, id: ID):
        asset = self._get_asset_by_id(self.assets, id)
        if asset.store.exists(asset):
            obj = asset.store.read(asset)
        else:
            kwargs = {id: self.materialize(id) for id in asset.deps}
            obj = asset.fun(**kwargs)
            asset.store.write(asset, obj)

        return obj

    @staticmethod
    def _get_asset_by_id(assets: list[Asset], id: ID):
        matches = [x for x in assets if x.id == id]
        match len(matches):
            case 0:
                raise RuntimeError(f"No asset with id '{id}")
            case 1:
                return matches[0]
            case _:
                raise RuntimeError(f"Multiple assets with id '{id}'")


@dataclasses.dataclass
class Asset:
    catalog: Catalog
    store: Store
    id: str
    fun: Callable
    deps: list[str]


def asset(
    catalog: Catalog,
    store: Store,
    deps: list[str] | None = None,
    id: str | None = None,
):
    def decorator(fun: Callable):
        id_ = id or fun.__name__

        # register this asset
        catalog.register(
            store=store,
            id=id_,
            fun=fun,
            deps=deps or [],
        )

        def wrapper():
            return catalog.materialize(id_)

        return wrapper

    return decorator
