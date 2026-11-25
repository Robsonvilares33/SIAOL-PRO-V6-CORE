import pytest

from lotomaster import storage


def test_cleanup_refuses_monkeypatched_path_without_explicit_environment(tmp_path, monkeypatch):
    database = tmp_path / "sentinel.sqlite3"
    sentinels = {
        database: b"database sentinel",
        tmp_path / "sentinel.sqlite3-wal": b"wal sentinel",
        tmp_path / "sentinel.sqlite3-shm": b"shm sentinel",
    }
    for path, content in sentinels.items():
        path.write_bytes(content)

    monkeypatch.delenv("LOTOMASTER_DB_PATH", raising=False)
    monkeypatch.setattr(storage, "DB_PATH", database)

    with pytest.raises(RuntimeError, match="LOTOMASTER_DB_PATH explicitamente"):
        storage.clear_for_tests()

    for path, content in sentinels.items():
        assert path.read_bytes() == content


def test_cleanup_removes_database_and_sidecars_when_explicitly_configured(tmp_path, monkeypatch):
    database = tmp_path / "isolated.sqlite3"
    paths = [database, tmp_path / "isolated.sqlite3-wal", tmp_path / "isolated.sqlite3-shm"]
    for path in paths:
        path.write_bytes(b"temporary test data")

    monkeypatch.setenv("LOTOMASTER_DB_PATH", str(database))
    monkeypatch.setattr(storage, "DB_PATH", database)

    storage.clear_for_tests()

    assert all(not path.exists() for path in paths)


def test_cleanup_refuses_environment_path_mismatch_without_unlinking(tmp_path, monkeypatch):
    database = tmp_path / "patched.sqlite3"
    wal = tmp_path / "patched.sqlite3-wal"
    shm = tmp_path / "patched.sqlite3-shm"
    for path in (database, wal, shm):
        path.write_bytes(b"sentinel")

    monkeypatch.setenv("LOTOMASTER_DB_PATH", str(tmp_path / "different.sqlite3"))
    monkeypatch.setattr(storage, "DB_PATH", database)

    with pytest.raises(RuntimeError, match="não corresponde ao DB_PATH ativo"):
        storage.clear_for_tests()

    assert [path.read_bytes() for path in (database, wal, shm)] == [b"sentinel"] * 3


def test_cleanup_refuses_explicit_default_database_path(tmp_path, monkeypatch):
    database = tmp_path / "application.sqlite3"
    paths = [database, tmp_path / "application.sqlite3-wal", tmp_path / "application.sqlite3-shm"]
    for path in paths:
        path.write_bytes(b"default database sentinel")

    monkeypatch.setattr(storage, "_DEFAULT_DB", database)
    monkeypatch.setenv("LOTOMASTER_DB_PATH", str(database))
    monkeypatch.setattr(storage, "DB_PATH", database)

    with pytest.raises(RuntimeError, match="banco padrão do aplicativo"):
        storage.clear_for_tests()

    assert [path.read_bytes() for path in paths] == [b"default database sentinel"] * 3
