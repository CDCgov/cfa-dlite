import polars as pl
import pytest

from fiat import (
    Catalog,
    MemoryStore,
    ParquetStore,
    PickleStore,
    Product,
    Source,
    TomlStore,
)


def test_memory_store():
    calls = 0

    def f() -> str:
        nonlocal calls
        calls += 1
        return "return"

    catalog = Catalog()
    catalog.add_asset(Product(fun=f, store=MemoryStore()))

    assert catalog.get("f") == "return"
    assert calls == 1

    # second call should not run the computation
    catalog.get("f")
    assert calls == 1


def test_as_product():
    catalog = Catalog()

    @catalog.as_product(store=MemoryStore())
    def f() -> str:
        return "return"

    assert catalog.get("f") == "return"


def test_pickle_store(tmp_path):
    path = tmp_path / "f.pkl"
    catalog = Catalog()
    store = PickleStore(path)
    calls = 0

    @catalog.as_product(store)
    def f() -> str:
        nonlocal calls
        calls += 1
        return "return"

    # should compute and write to disk
    assert catalog.get("f") == "return"
    assert calls == 1
    assert path.exists()

    # should read from disk
    assert catalog.get("f") == "return"
    assert calls == 1


def test_parquet_store(tmp_path):
    catalog = Catalog()

    @catalog.as_product(ParquetStore(tmp_path / "f.parquet"))
    def f() -> pl.DataFrame:
        return pl.DataFrame({"x": [1, 2, 3]})

    assert isinstance(catalog.get("f"), pl.DataFrame)


def test_parquet_store_fail(tmp_path):
    catalog = Catalog()

    # should fail if wrong data type
    @catalog.as_product(ParquetStore(tmp_path / "g.parquet"))
    def g() -> str:
        return "strings can't go in parquets"

    with pytest.raises(ValueError, match="parquet"):
        catalog.get("g")


def test_asset_can_call_other_assets():
    catalog = Catalog()

    @catalog.as_product(store=MemoryStore())
    def one() -> int:
        return 1

    @catalog.as_product(store=MemoryStore())
    def two(one: int) -> int:
        return one + one

    # asset calls other assets
    assert catalog.get("two") == 2


def test_product_functions_pass_through():
    catalog = Catalog()

    @catalog.as_product(store=MemoryStore())
    def add(x, y):
        return x + y

    assert add(1, 2) == 3

    # asset call fails because of missing dependencies
    with pytest.raises(RuntimeError, match="not among cataloged assets"):
        catalog.get("add")


def test_postorder_dfs():
    assert Catalog._postorder_dfs("a", {"a": ["b", "c"], "b": ["d"], "d": ["e"]}) == [
        "e",
        "d",
        "b",
        "c",
        "a",
    ]


def test_source(tmp_path):
    my_config = """
[parameters]
beta = 0.5
gamma = 2.0
"""

    config_path = tmp_path / "config.toml"
    with open(config_path, "w") as f:
        f.write(my_config)

    catalog = Catalog()
    catalog.add_asset(Source(id="config", store=TomlStore(config_path)))

    @catalog.as_product(MemoryStore())
    def r0(config):
        return config["parameters"]["beta"] / config["parameters"]["gamma"]

    assert catalog.get("r0") == 0.25
