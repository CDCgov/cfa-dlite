import polars as pl
import pytest

from fiat import Catalog, MemoryStore, ParquetStore, PickleStore


def test_memory_store():
    catalog = Catalog()
    store = MemoryStore()
    calls = 0

    @catalog.as_asset(store)
    def f() -> str:
        nonlocal calls
        calls += 1
        return "return value"

    assert f() == "return value"
    assert calls == 1

    # second call should do nothing
    f()
    assert calls == 1


def test_pickle_store(tmp_path):
    path = tmp_path / "f.pkl"
    catalog = Catalog()
    store = PickleStore(path)
    calls = 0

    @catalog.as_asset(store)
    def f() -> str:
        nonlocal calls
        calls += 1
        return "return value"

    assert f() == "return value"
    assert (path).exists()
    assert calls == 1

    # should read from disk
    assert f() == "return value"
    assert calls == 1


def test_parquet_store(tmp_path):
    catalog = Catalog()

    @catalog.as_asset(ParquetStore(tmp_path / "f.parquet"))
    def f() -> pl.DataFrame:
        return pl.DataFrame({"x": [1, 2, 3]})

    obj = f()
    assert isinstance(obj, pl.DataFrame)


def test_parquet_store_fail(tmp_path):
    catalog = Catalog()

    # should fail if wrong data type
    @catalog.as_asset(ParquetStore(tmp_path / "g.parquet"))
    def g() -> str:
        return "strings can't go in parquets"

    with pytest.raises(ValueError, match="parquet"):
        g()
