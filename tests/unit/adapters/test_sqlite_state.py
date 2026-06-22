import threading

from lbb.adapters.sqlite_state import SqliteStateStore


def test_mark_and_read_engraved_keys(tmp_path):
    s = SqliteStateStore(tmp_path / "state.sqlite")
    assert s.engraved_keys("306-1") == set()
    s.mark_engraved("306-1", "engraving/a Front.pdf", True)
    s.mark_engraved("306-1", "engraving/a Back.pdf", True)
    assert s.engraved_keys("306-1") == {"engraving/a Front.pdf", "engraving/a Back.pdf"}


def test_unmark_removes_key(tmp_path):
    s = SqliteStateStore(tmp_path / "state.sqlite")
    s.mark_engraved("306-1", "k1", True)
    s.mark_engraved("306-1", "k1", False)
    assert s.engraved_keys("306-1") == set()


def test_mark_is_idempotent(tmp_path):
    s = SqliteStateStore(tmp_path / "state.sqlite")
    s.mark_engraved("306-1", "k1", True)
    s.mark_engraved("306-1", "k1", True)
    assert s.engraved_keys("306-1") == {"k1"}


def test_survives_reopen(tmp_path):
    db = tmp_path / "state.sqlite"
    SqliteStateStore(db).mark_engraved("306-1", "k1", True)
    assert SqliteStateStore(db).engraved_keys("306-1") == {"k1"}


def test_usable_from_another_thread(tmp_path):
    """pywebview dispatches bridge calls on a worker thread; the connection is
    created on the main thread. This must not raise ProgrammingError."""
    s = SqliteStateStore(tmp_path / "state.sqlite")
    errors = []

    def worker():
        try:
            s.mark_engraved("306-1", "k1", True)
            s.engraved_keys("306-1")
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert errors == [], errors
    assert s.engraved_keys("306-1") == {"k1"}
