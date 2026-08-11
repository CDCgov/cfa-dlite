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


try:
    import polars as pl

    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False

type Asset = Source | Product


class Source:
    def __init__(self, id: ID, store: Store):
        self.id = id
        self.store = store
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
    def is_materialized(self) -> bool:
        pass

    @abstractmethod
    def read(self) -> Any:
        pass

    @abstractmethod
    def write(self, obj) -> None:
        """Write the materialized value to the store"""
        pass

    @abstractmethod
    def mtime(self) -> float:
        pass


class MemoryStore(Store):
    def __init__(self):
        self._is_materialized = False
        self._value = None
        self._mtime = None

    def is_materialized(self) -> bool:
        return self._is_materialized

    def read(self):
        if self.is_materialized():
            return self._value
        else:
            raise RuntimeError("Asset not materialized")

    def mtime(self):
        if self.is_materialized():
            return self._mtime
        else:
            raise RuntimeError("Asset not materialized")

    def write(self, obj):
        self._is_materialized = True
        self._value = obj
        self._mtime = time.time()


class FileStore(Store):
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def is_materialized(self) -> bool:
        return self.path.exists()

    def read(self):
        if self.is_materialized():
            return self._read_file(self.path)
        else:
            raise RuntimeError("Asset not materialized")

    @staticmethod
    @abstractmethod
    def _read_file(path: Path) -> Any:
        pass

    def mtime(self) -> float:
        if self.is_materialized():
            return self.path.stat().st_mtime
        else:
            raise RuntimeError("Asset not materialized")


class PickleStore(FileStore):
    @staticmethod
    def _read_file(path: Path):
        with open(path, "rb") as f:
            return pickle.load(f)

    def write(self, obj):
        with open(self.path, "wb") as f:
            pickle.dump(obj, f)


class ParquetStore(FileStore):
    def __init__(self, path: str | Path):
        super().__init__(path=path)

        if not HAS_POLARS:
            raise ImportError("dlite[polars] is required for ParquetStore")

    @staticmethod
    def _read_file(path: Path):
        return pl.read_parquet(path)

    def write(self, obj: pl.DataFrame):
        if not isinstance(obj, pl.DataFrame):
            raise ValueError(
                f"Cannot write '{obj}' of type {type(obj)} to parquet store"
            )
        obj.write_parquet(self.path)


class TomlStore(FileStore):
    @staticmethod
    def _read_file(path: Path):
        with open(path, "rb") as f:
            return tomllib.load(f)

    def write(self, _):
        raise NotImplementedError("Writing toml is not implemented")


class Catalog:
    def __init__(self):
        self.assets: dict[ID, Asset] = {}

    def _get_asset(self, id: ID):
        """Get the asset, not its value"""
        if id not in self.assets:
            raise RuntimeError(f"Unknown asset ID {id} among {self.assets.keys()}")

        return self.assets[id]

    def add_asset(self, asset: Asset):
        """Add an asset to the catalog"""
        if asset.id in self.assets:
            raise RuntimeError(f"Duplicated asset ID '{asset.id}'")

        self.assets[asset.id] = asset

    def as_product(self, store: Store):
        """Product function wrapper"""

        def decorator(fun: Callable):
            """Add a Product to the catalog, using this function"""
            self.add_asset(Product(fun=fun, store=store))

            # pass through the original function
            def wrapper(*args, **kwargs):
                return fun(*args, **kwargs)

            return wrapper

        return decorator

    def get(self, id: ID) -> Any:
        """Get the value of an asset"""
        asset = self._get_asset(id)

        if isinstance(asset, Product):
            self._ensure_fresh(asset)

        return self._read_materialized_value(asset)

    def _read_materialized_value(self, asset: Asset) -> Any:
        if asset.store.is_materialized():
            return asset.store.read()
        else:
            raise RuntimeError(f"Asset {asset.id} is not materialized")

    def _ensure_fresh(self, product: Product) -> None:
        """Ensure `id` and its ancestors are fresh"""
        # map each asset to its dependencies
        deps_map = {asset.id: asset.deps for asset in self.assets.values()}

        # get an ordered list of ancestors for the target product
        ancestors = self._postorder_dfs(root=product.id, deps_map=deps_map)

        # ensure all ancestors are known
        if missing_ids := set(ancestors) - set(self.assets.keys()):
            raise RuntimeError(
                f"Product {product.id} has ancestors {missing_ids} that"
                " are not among cataloged assets"
            )

        for ancestor in ancestors:
            asset = self._get_asset(ancestor)

            if isinstance(asset, Source) and asset.store.is_materialized():
                pass
            elif isinstance(asset, Source):
                raise RuntimeError(f"Source {asset.id} is not materialized")
            elif isinstance(asset, Product) and self._is_fresh(asset):
                pass
            elif isinstance(asset, Product):
                self._materialize(asset)
            else:
                raise RuntimeError(f"Unexpected state: {asset.id}")

    def _is_fresh(self, asset: Asset) -> bool:
        if not asset.store.is_materialized():
            # not materialized -> stale
            return False
        else:
            deps = [self._get_asset(dep) for dep in asset.deps]

            if non_mat_deps := [dep for dep in deps if not dep.store.is_materialized()]:
                raise RuntimeError(
                    f"Asset {asset.id} has un-materialized deps {non_mat_deps}"
                )

            if len(deps) == 0:
                return True
            else:
                mtime = asset.store.mtime()
                dep_mtimes = [dep.store.mtime() for dep in deps]

                if any(dep_mtime is None for dep_mtime in dep_mtimes):
                    raise RuntimeError(
                        f"Asset {asset.id} has deps with un-materialized mtimes"
                    )

                return mtime > max(dep_mtimes)

    def _materialize(self, product: Product):
        """Compute the Product's value"""
        args = [
            self._read_materialized_value(self._get_asset(id)) for id in product.deps
        ]
        value = product.fun(*args)
        product.store.write(value)

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
                raise RuntimeError(f"Node {node} has bad state {state[node]}")

        visit(root)
        return order
