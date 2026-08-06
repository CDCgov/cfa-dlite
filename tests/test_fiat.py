import polars as pl
import pytest

from fiat import Catalog, MemoryStore, ParquetStore, PickleStore, asset


def test_memory_store():
    catalog = Catalog()
    store = MemoryStore()
    calls = 0

    @asset(catalog, store)
    def f() -> str:
        nonlocal calls
        calls += 1
        return "return value"

    assert f() == "return value"
    assert calls == 1

    # second call should do nothing
    f()
    assert calls == 1

    # peek inside the store
    assert store.assets == {"f": "return value"}


def test_pickle_store(tmp_path):
    catalog = Catalog()
    store = PickleStore(tmp_path)
    calls = 0

    @asset(catalog, store)
    def f() -> str:
        nonlocal calls
        calls += 1
        return "return value"

    assert f() == "return value"
    assert (tmp_path / "f.pkl").exists()
    assert calls == 1

    # should read from disk
    assert f() == "return value"
    assert calls == 1


def test_parquet_store(tmp_path):
    catalog = Catalog()
    store = ParquetStore(tmp_path)

    @asset(catalog, store)
    def f() -> pl.DataFrame:
        return pl.DataFrame({"x": [1, 2, 3]})

    obj = f()
    assert isinstance(obj, pl.DataFrame)

    # should fail if wrong data type
    @asset(catalog, store)
    def g() -> str:
        return "strings can't go in parquets"

    with pytest.raises(ValueError, match="parquet"):
        g()
