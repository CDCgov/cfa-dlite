from __future__ import annotations

import dataclasses
import inspect
import pickle
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

from returns.maybe import Maybe, Nothing, Some

type ID = Callable

try:
    import polars as pl

    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False


@dataclasses.dataclass
class Asset:
    fun: Callable
    store: Store


class Store(ABC):
    @abstractmethod
    def read(self) -> Maybe:
        pass

    @abstractmethod
    def write(self, obj) -> None:
        pass


class NullStore(Store):
    def read(self):
        return Nothing

    def write(self, _):
        pass


class MemoryStore(Store):
    def __init__(self):
        self._read_value = Nothing

    def read(self):
        return self._read_value

    def write(self, obj):
        self._read_value = Some(obj)


class FileStore(Store):
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self):
        if self.path.exists():
            return Some(self._read_file())
        else:
            return Nothing

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
        self.aliases = {}

    def add(self, asset: Asset):
        if len(inspect.signature(asset.fun).parameters) != 0:
            raise RuntimeError(f"Asset {asset.fun.__name__} has >0 parameters")

        id = self._fun_id(asset.fun)
        if id in self.assets:
            raise RuntimeError(f"Duplicated asset ID '{id}'")

        self.assets[id] = asset

    def get(self, id: ID):
        # calls to wrapper functions are rerouted to their inner functions
        if id in self.aliases:
            id = self.aliases[id]

        if id not in self.assets:
            raise RuntimeError(f"Unknown asset ID {id} among {self.assets.keys()}")

        asset = self.assets[id]
        match asset.store.read():
            case Some(obj):
                return obj
            case _:
                obj = self._build(id)
                asset.store.write(obj)
                return obj

    def _build(self, id: ID):
        asset = self.assets[id]
        return asset.fun()

    def asset(self, store: Store):
        def decorator(fun: Callable):
            """Add this function as an asset to the catalog"""
            id = self._fun_id(fun)
            self.add(Asset(fun=fun, store=store))
            print(f"{fun=}")

            def wrapper():
                """Return the asset's materialized value"""
                return self.get(id)

            self.aliases[wrapper] = fun
            print(f"{wrapper=}")
            return wrapper

        print(f"{decorator=}")
        return decorator

    @staticmethod
    def _fun_id(fun: Callable) -> ID:
        return fun
