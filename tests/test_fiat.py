import polars as pl
import pytest

from fiat import Asset, Catalog, MemoryStore, ParquetStore, PickleStore


def test_memory_store():
    catalog = Catalog()
    store = MemoryStore()
    calls = 0

    @catalog.asset(store)
    def f() -> str:
        nonlocal calls
        calls += 1
        return "return value"

    assert catalog.get("f") == "return value"
    assert calls == 1

    # second call should do nothing
    catalog.get("f")
    assert calls == 1


def test_pickle_store(tmp_path):
    path = tmp_path / "f.pkl"
    catalog = Catalog()
    store = PickleStore(path)
    calls = 0

    @catalog.asset(store)
    def f() -> str:
        nonlocal calls
        calls += 1
        return "return value"

    assert catalog.get("f") == "return value"
    assert (path).exists()
    assert calls == 1

    # should read from disk
    assert catalog.get("f") == "return value"
    assert calls == 1


def test_parquet_store(tmp_path):
    catalog = Catalog()

    @catalog.asset(ParquetStore(tmp_path / "f.parquet"))
    def f() -> pl.DataFrame:
        return pl.DataFrame({"x": [1, 2, 3]})

    assert isinstance(catalog.get("f"), pl.DataFrame)


def test_parquet_store_fail(tmp_path):
    catalog = Catalog()

    # should fail if wrong data type
    @catalog.asset(ParquetStore(tmp_path / "g.parquet"))
    def g() -> str:
        return "strings can't go in parquets"

    with pytest.raises(ValueError, match="parquet"):
        catalog.get("g")


def test_manual_asset():
    catalog = Catalog()
    calls = 0

    def f() -> str:
        nonlocal calls
        calls += 1
        return "return value"

    catalog.add_asset(Asset(fun=f, store=MemoryStore()))

    assert catalog.get("f") == "return value"
    assert calls == 1
    catalog.get("f")
    assert calls == 1


def test_get_by_function_manual():
    catalog = Catalog()

    def f():
        return 1

    catalog.add_asset(Asset(fun=f, store=MemoryStore()))

    assert catalog.get("f") == 1


def test_get_by_function_wrap():
    catalog = Catalog()

    @catalog.asset(store=MemoryStore())
    def f():
        return 1

    assert catalog.get("f") == 1


def test_asset_deps():
    catalog = Catalog()

    @catalog.asset(MemoryStore())
    def one():
        return 1

    @catalog.asset(MemoryStore())
    def two():
        return 2

    @catalog.asset(MemoryStore())
    def three(one, two) -> int:
        return one + two

    assert catalog.get("three") == 3


def test_calling_asset_passes_through():
    catalog = Catalog()

    @catalog.asset(MemoryStore())
    def one():
        return 1

    @catalog.asset(MemoryStore())
    def two(one):
        return one + one

    assert two(2) == 4


def test_postorder_dfs():
    assert Catalog._postorder_dfs("a", {"a": ["b", "c"], "b": ["d"], "d": ["e"]}) == [
        "e",
        "d",
        "b",
        "c",
        "a",
    ]
