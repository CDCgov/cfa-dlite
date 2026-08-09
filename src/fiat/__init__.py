from __future__ import annotations

import inspect
import pickle
import time
import tomllib
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

type ID = str
type _StoreOutcome = tuple[bool] | tuple[bool, Any]

try:
    import polars as pl

    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False

type Asset = Source | Product


class Source:
    def __init__(self, store: Store, id: ID):
        self.store = store
        self.id = id
        self.deps = []


class Product:
    def __init__(self, fun: Callable, store: Store, id: ID | None = None):
        self.fun = fun
        self.store = store
        self.id = id or self._fun_id(fun)
        # dependency assets are listed in the function signature
        self.deps: list[str] = list(inspect.signature(fun).parameters)

    @staticmethod
    def _fun_id(fun: Callable) -> ID:
        """Asset ID is the name of the function"""
        return fun.__name__


class Store(ABC):
    @abstractmethod
    def read(self) -> _StoreOutcome:
        pass

    @abstractmethod
    def write(self, obj) -> None:
        pass

    @abstractmethod
    def mtime(self) -> float | None:
        pass


class NullStore(Store):
    def read(self):
        return None

    def write(self, _):
        pass

    def mtime(self):
        return None


class MemoryStore(Store):
    def __init__(self):
        self._materialized = False
        self._value = None
        self._mtime = None

    def read(self) -> _StoreOutcome:
        if self._materialized:
            return (True, self._value)
        else:
            return (False,)

    def write(self, obj):
        self._materialized = True
        self._value = obj
        self._mtime = time.time()

    def mtime(self):
        return self._mtime


class FileStore(Store):
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self) -> _StoreOutcome:
        if self.path.exists():
            return (True, self._read_file())
        else:
            return (False,)

    @abstractmethod
    def _read_file(self):
        pass

    def mtime(self):
        if self.path.exists():
            return self.path.stat().st_mtime
        else:
            return None


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


class TomlStore(FileStore):
    def _read_file(self):
        with open(self.path, "rb") as f:
            return tomllib.load(f)

    def write(self, _):
        raise NotImplementedError()


class Catalog:
    def __init__(self):
        self.assets: dict[ID, Asset] = {}
        self.aliases = {}

    def _get_asset(self, id: ID):
        """Get the asset entry"""
        if id not in self.assets:
            raise RuntimeError(f"Unknown asset ID {id} among {self.assets.keys()}")

        return self.assets[id]

    def add(self, asset: Asset):
        """Add an Asset to the catalog"""
        if asset.id in self.assets:
            raise RuntimeError(f"Duplicated asset ID '{asset.id}'")

        self.assets[asset.id] = asset

    def product(self, store: Store):
        """Product function wrapper"""

        def decorator(fun: Callable):
            """Add a Product to the catalog, using this function"""
            self.add(Product(fun=fun, store=store))

            # pass through the original function
            def wrapper(*args, **kwargs):
                return fun(*args, **kwargs)

            return wrapper

        return decorator

    def get(self, id: ID):
        """Get the value of an asset"""
        asset = self._get_asset(id)

        if isinstance(asset, Product):
            self._ensure_fresh(product)

        value = asset.store.read()

        if not (len(value) == 2 and value[0]):
            raise RuntimeError(f"Asset {id} was not materialized in freshness check")

        return value[1]

    def _ensure_fresh(self, product: Product):
        """Ensure `id` and its ancestors are fresh"""
        # map each asset to its dependencies
        deps_map = {asset.id: asset.deps for id, asset in self.assets.items()}
        # get an ordered list of ancestors for the target asset
        ancestors = self._postorder_dfs(root=product.id, deps_map=deps_map)

        for ancestor in ancestors:
            asset = self._get_asset(ancestor)
            if self._is_stale(asset):
                self._materialize(product.id)

    def _is_stale(self, asset: Asset) -> bool:
        """Asset is not materialized, or it is older than a dependency"""
        mtime = asset.store.mtime()

        if mtime is None:
            return True
        elif mtime is not None and len(asset.deps) == 0:
            return False
        elif mtime is not None and len(asset.deps) > 0:
            dep_mtimes = [self._get_asset(dep).store.mtime() for dep in asset.deps]
            if any(dep_mtime is None for dep_mtime in dep_mtimes):
                raise RuntimeError(
                    f"Asset {asset.id} has un-materialized dependencies while ensuring freshness"
                )

            max_dep_mtime = self._max_no_nones(dep_mtimes)

            return mtime < max_dep_mtime
        else:
            raise RuntimeError(f"Bad state: {mtime=} and {asset.deps=}")

    def _materialize(self, product: Product):
        """Compute the Product's value"""
        if missing_ids := set(product.deps) - set(self.assets.keys()):
            raise RuntimeError(
                f"Product {id} requires assets {missing_ids},"
                " but these are not in the catalog"
            )

        args = [self.get(id) for id in product.deps]
        assert all(arg is not None for arg in args)
        value = product.fun(*args)
        product.store.write(value)

    @staticmethod
    def _max_no_nones(lst: list[float | None]) -> float:
        assert all(isinstance(x, float) for x in lst)
        return max([x for x in lst if x is not None])

    @staticmethod
    def _postorder_dfs(root: str, deps_map: dict[str, list[str]]):
        """Post-ordered depth-first search"""
        assert root in deps_map
        state = {}
        order = []

        def visit(node):
            if node not in state:
                state[node] = "visiting"

                if node in deps_map:
                    for dep in deps_map[node]:
                        visit(dep)

                state[node] = "done"
                order.append(node)
            elif state[node] == "visiting":
                raise RuntimeError(f"Cycle detected at {node}")
            elif state[node] == "done":
                return
            else:
                RuntimeError(f"Node {node} has bad state {state[node]}")

        visit(root)
        return order
