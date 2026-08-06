import fiat


def test_memory_storage():
    storage = fiat.MemoryStorage()
    registry = fiat.AssetRegistry(storage)
    calls = 0

    @fiat.asset(registry)
    def f() -> str:
        nonlocal calls
        calls += 1
        return "return value"

    assert f() == "return value"
    assert calls == 1

    # second call should do nothing
    f()
    assert calls == 1

    assert storage.assets == {"f": "return value"}


def test_file_storage(tmp_path):
    registry = fiat.AssetRegistry(fiat.FileStorage(tmp_path))
    calls = 0

    @fiat.asset(registry)
    def f() -> str:
        nonlocal calls
        calls += 1
        return "return value"

    assert f() == "return value"
    assert (tmp_path / "f.pkl").exists()
    assert calls == 1

    # should read from disk
    f()
    assert calls == 1
