from __future__ import annotations

import dataclasses
import pickle
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

type ID = str

try:
    import polars as pl

    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False


@dataclasses.dataclass
class Asset:
    id: str
    store: Store
    fun: Callable
    deps: list[str]

    def materialize(self):
        outcome = self.store.read()
        if outcome.exists:
            obj = outcome.obj
        else:
            obj = self.fun()
            self.store.write(obj)

        return obj


@dataclasses.dataclass
class _StoreOutcome:
    exists: bool
    obj: Any = None


class Store(ABC):
    @abstractmethod
    def read(self) -> _StoreOutcome:
        pass

    @abstractmethod
    def write(self, obj):
        pass


class NullStore(Store):
    def read(self):
        return _StoreOutcome(exists=False)

    def write(self, _):
        pass


class MemoryStore(Store):
    def __init__(self):
        self.exists = False
        self.obj = None

    def read(self):
        return _StoreOutcome(exists=self.exists, obj=self.obj)

    def write(self, obj):
        self.exists = True
        self.obj = obj


class FileStore(Store):
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self):
        if self.path.exists():
            exists = True
            obj = self._read_file()
        else:
            exists = False
            obj = None

        return _StoreOutcome(exists=exists, obj=obj)

    @abstractmethod
    def _read_file(self):
        pass


class PickleStore(FileStore):
    def _read_file(self):
        with open(self.path, "rb") as f:
            return pickle.load(f)

    def write(self, obj):
        with open(self.path, "wb") as f:
            pickle.dump(obj, f)


class ParquetStore(FileStore):
    def __post_init__(self):
        if not HAS_POLARS:
            raise ImportError("fiat[polars] is required for ParquetStore")

    def _read_file(self):
        return pl.read_parquet(self.path)

    def write(self, obj: pl.DataFrame):
        if not isinstance(obj, pl.DataFrame):
            raise ValueError(
                f"Cannot write '{obj}' of type {type(obj)} to parquet store"
            )
        obj.write_parquet(self.path)


class Catalog:
    def __init__(self):
        self.assets: dict[ID, Asset] = {}

    def asset(
        self,
        store: Store,
        deps: list[str] | None = None,
        id: str | None = None,
    ):
        def decorator(fun: Callable):
            """Register this asset"""
            id_ = id or fun.__name__
            deps_ = deps or []

            if id_ in self.assets:
                raise RuntimeError(f"Duplicated asset ID '{id}'")

            asset = Asset(store=store, id=id_, fun=fun, deps=deps_)
            self.assets[id_] = asset

            def wrapper():
                """Return the asset's materialized value"""
                return self.materialize(id_)

            return wrapper

        return decorator

    def materialize(self, id: ID):
        asset = self.assets[id]
        return asset.materialize()
