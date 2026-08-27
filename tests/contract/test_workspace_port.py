"""Contract tests for WorkspacePort / SqliteWorkspaceAdapter (ADR-044)."""

from backend.adapters.workspace.sqlite_adapter import SqliteWorkspaceAdapter


def make_workspace_adapter():
    return SqliteWorkspaceAdapter(":memory:")


def test_create_then_get():
    w = make_workspace_adapter()
    workspace_id = w.create_workspace("user1", "Marketing")
    got = w.get_workspace(workspace_id, "user1")
    assert got is not None
    assert got.name == "Marketing"
    assert got.owner_id == "user1"


def test_get_returns_none_for_unknown_id():
    w = make_workspace_adapter()
    assert w.get_workspace("not-a-real-id", "user1") is None


def test_get_returns_none_for_wrong_owner():
    """Same isolation guarantee StoragePort already enforces — not
    found and wrong-owner return the identical None, no distinction
    an attacker could use to enumerate other users' workspace ids."""
    w = make_workspace_adapter()
    workspace_id = w.create_workspace("user1", "Marketing")
    assert w.get_workspace(workspace_id, "user2") is None


def test_list_workspaces_scoped_to_owner():
    w = make_workspace_adapter()
    w.create_workspace("user1", "Marketing")
    w.create_workspace("user1", "Sales")
    w.create_workspace("user2", "Someone Else's Workspace")
    names = {ws.name for ws in w.list_workspaces("user1")}
    assert names == {"Marketing", "Sales"}


def test_list_workspaces_orders_most_recently_updated_first():
    w = make_workspace_adapter()
    first = w.create_workspace("user1", "First")
    w.create_workspace("user1", "Second")
    w.rename_workspace(first, "user1", "First (renamed)")
    names_in_order = [ws.name for ws in w.list_workspaces("user1")]
    assert names_in_order[0] == "First (renamed)"


def test_rename_workspace():
    w = make_workspace_adapter()
    workspace_id = w.create_workspace("user1", "Old Name")
    renamed = w.rename_workspace(workspace_id, "user1", "New Name")
    assert renamed is True
    assert w.get_workspace(workspace_id, "user1").name == "New Name"


def test_rename_wrong_owner_returns_false_and_does_not_rename():
    w = make_workspace_adapter()
    workspace_id = w.create_workspace("user1", "Original")
    renamed = w.rename_workspace(workspace_id, "user2", "Hijacked")
    assert renamed is False
    assert w.get_workspace(workspace_id, "user1").name == "Original"


def test_delete_workspace():
    w = make_workspace_adapter()
    workspace_id = w.create_workspace("user1", "Temp")
    deleted = w.delete_workspace(workspace_id, "user1")
    assert deleted is True
    assert w.get_workspace(workspace_id, "user1") is None


def test_delete_wrong_owner_returns_false_and_does_not_delete():
    w = make_workspace_adapter()
    workspace_id = w.create_workspace("user1", "Protected")
    deleted = w.delete_workspace(workspace_id, "user2")
    assert deleted is False
    assert w.get_workspace(workspace_id, "user1") is not None


def test_delete_unknown_id_returns_false_not_raise():
    w = make_workspace_adapter()
    assert w.delete_workspace("not-a-real-id", "user1") is False
