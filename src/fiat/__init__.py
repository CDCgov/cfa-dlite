import dataclasses
import inspect
import pickle
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Literal

try:
    import polars as pl

    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False

Formats = Literal["pickle", "parquet"]


class AssetStorage(ABC):
    @abstractmethod
    def exists(self, entry):
        pass

    @abstractmethod
    def read(self, entry):
        pass

    @abstractmethod
    def write(self, entry, asset):
        pass


class MemoryStorage(AssetStorage):
    def __init__(self):
        self.assets = {}

    def exists(self, entry):
        return entry.id in self.assets

    def read(self, entry):
        return self.assets[entry.id]

    def write(self, entry, asset):
        self.assets[entry.id] = asset


class FileStorage(AssetStorage):
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)

    def path(self, entry):
        ext = {"pickle": "pkl", "parquet": "parquet"}[entry.format]
        return self.data_dir / f"{entry.id}.{ext}"

    def exists(self, entry):
        return self.path(entry).exists()

    def read(self, entry):
        path = self.path(entry)
        match entry.format:
            case "pickle":
                with open(path, "rb") as f:
                    return pickle.load(f)
            case "parquet":
                if HAS_POLARS:
                    return pl.read_parquet(path)
                raise ImportError("polars is required")
            case _:
                raise NotImplementedError(
                    f"no read implementation for format '{entry.format}'"
                )

    def write(self, entry, asset):
        path = self.path(entry)
        match entry.format:
            case "pickle":
                with open(path, "wb") as f:
                    pickle.dump(asset, f)
            case "parquet":
                if HAS_POLARS:
                    assert isinstance(asset, pl.DataFrame)
                    asset.write_parquet(path)
                else:
                    raise ImportError("polars is required")
            case _:
                raise NotImplementedError(
                    f"no write implementation for format '{entry.format}'"
                )


class AssetRegistry:
    def __init__(self, storage: AssetStorage):
        self.storage = storage
        self.entries: list[AssetEntry] = []

    def register(self, entry):
        self.entries.append(entry)

    def get(self, id: str):
        matches = [x for x in self.entries if x.id == id]
        match len(matches):
            case 0:
                raise RuntimeError(f"No asset with id '{id}")
            case 1:
                return matches[0].get()
            case _:
                raise RuntimeError(f"Multiple assets with id '{id}'")


@dataclasses.dataclass
class AssetEntry:
    registry: AssetRegistry
    id: str
    fun: Callable
    deps: list[str]
    format: str

    def __post_init__(self):
        # validate signature
        signature_parameters = set(inspect.signature(self.fun).parameters)
        if signature_parameters != set(self.deps):
            raise RuntimeError(
                f"deps {self.deps} is not equal to parameters {signature_parameters}"
            )

    def get(self):
        if self.registry.storage.exists(self):
            return self.registry.storage.read(self)

        kwargs = {id: self.registry.get(id) for id in self.deps}
        asset = self.fun(**kwargs)
        self.registry.storage.write(self, asset)
        return asset


def asset(
    registry: AssetRegistry, deps: list[str] | None = None, format: Formats = "pickle"
):
    if deps is None:
        deps = []

    def decorator(fun: Callable):
        # register this asset
        id = fun.__name__

        registry.register(
            AssetEntry(
                registry=registry,
                id=id,
                fun=fun,
                deps=deps,
                format=format,
            )
        )

        def wrapper():
            return registry.get(id)

        return wrapper

    return decorator
