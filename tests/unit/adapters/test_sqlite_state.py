from lbb.adapters.sqlite_state import SqliteStateStore
from lbb.core.fulfillment import OrderStatus


def test_mark_side_then_read_back(tmp_path):
    s = SqliteStateStore(tmp_path / "state.sqlite")
    s.mark_side("306-1", "A", "Front", True)
    assert s.engraved_sides("306-1") == {("A", "Front")}


def test_unmark_side_removes_it(tmp_path):
    s = SqliteStateStore(tmp_path / "state.sqlite")
    s.mark_side("306-1", "A", "Front", True)
    s.mark_side("306-1", "A", "Front", False)
    assert s.engraved_sides("306-1") == set()


def test_override_set_get_clear(tmp_path):
    s = SqliteStateStore(tmp_path / "state.sqlite")
    assert s.get_override("306-1") is None
    s.set_override("306-1", OrderStatus.HOLD)
    assert s.get_override("306-1") is OrderStatus.HOLD
    s.set_override("306-1", None)
    assert s.get_override("306-1") is None


def test_comments_append_in_order(tmp_path):
    s = SqliteStateStore(tmp_path / "state.sqlite")
    s.add_comment("306-1", "re-engrave back side", "A. Fink")
    s.add_comment("306-1", "fixed", "A. Fink")
    texts = [c.text for c in s.comments("306-1")]
    assert texts == ["re-engrave back side", "fixed"]


def test_state_persists_across_reopen(tmp_path):
    db = tmp_path / "state.sqlite"
    SqliteStateStore(db).mark_side("306-1", "A", "Front", True)
    assert SqliteStateStore(db).engraved_sides("306-1") == {("A", "Front")}
