import progress_service


def _reset_progress_state(monkeypatch, progress_file):
    monkeypatch.setattr(progress_service, "PROGRESS_STORE_FILE", str(progress_file))
    monkeypatch.setattr(progress_service, "progress_store", {})
    monkeypatch.setattr(progress_service, "_progress_store_dirty", False)
    monkeypatch.setattr(progress_service, "_last_persist_at", 0.0)


def test_count_active_tasks_ignores_terminal_statuses(tmp_path, monkeypatch):
    progress_file = tmp_path / "progress_store.json"
    _reset_progress_state(monkeypatch, progress_file)

    progress_service.set_progress("task-1", progress_service.create_progress_entry("https://a", "m4b"))
    progress_service.set_progress("task-2", {"status": "success", "updated_at": 1})
    progress_service.set_progress("task-3", {"status": "interrupted", "updated_at": 1})

    assert progress_service.count_active_tasks() == 1


def test_cleanup_expired_progress_removes_terminal_entries(tmp_path, monkeypatch):
    progress_file = tmp_path / "progress_store.json"
    _reset_progress_state(monkeypatch, progress_file)
    monkeypatch.setattr(progress_service, "progress_store", {
        "old": {"status": "success", "updated_at": 0},
        "active": {"status": "processing", "updated_at": 9999999999},
    })

    deleted = progress_service.cleanup_expired_progress(expire_seconds=1)

    assert deleted == ["old"]
    assert "old" not in progress_service.progress_store
    assert "active" in progress_service.progress_store


def test_get_progress_returns_updated_at_field(tmp_path, monkeypatch):
    progress_file = tmp_path / "progress_store.json"
    _reset_progress_state(monkeypatch, progress_file)

    progress_service.set_progress("task-1", progress_service.create_progress_entry("https://a", "m4b"))

    payload = progress_service.get_progress("task-1")

    assert "updated_at" in payload
    assert payload["updated_at"] > 0


def test_nonterminal_progress_updates_are_debounced_until_due(tmp_path, monkeypatch):
    progress_file = tmp_path / "progress_store.json"
    _reset_progress_state(monkeypatch, progress_file)
    monkeypatch.setattr(progress_service, "PROGRESS_PERSIST_MIN_INTERVAL_SECONDS", 10.0)

    fake_now = [100.0]
    monkeypatch.setattr(progress_service.time, "time", lambda: fake_now[0])

    write_calls = []
    original_write = progress_service._write_progress_store_unlocked

    def counting_write(now=None):
        write_calls.append(now if now is not None else fake_now[0])
        return original_write(now)

    monkeypatch.setattr(progress_service, "_write_progress_store_unlocked", counting_write)

    progress_service.set_progress("task-1", progress_service.create_progress_entry("https://a", "m4b"))
    progress_service.update_progress_entry("task-1", status="processing", percent=5.0)
    progress_service.update_progress_entry("task-1", percent=10.0)

    assert len(write_calls) == 1
    assert progress_service._progress_store_dirty is True

    fake_now[0] = 111.0
    payload = progress_service.get_progress("task-1")

    assert payload["percent"] == 10.0
    assert len(write_calls) == 2
    assert progress_service._progress_store_dirty is False


def test_terminal_progress_update_forces_immediate_persist(tmp_path, monkeypatch):
    progress_file = tmp_path / "progress_store.json"
    _reset_progress_state(monkeypatch, progress_file)
    monkeypatch.setattr(progress_service, "PROGRESS_PERSIST_MIN_INTERVAL_SECONDS", 10.0)

    fake_now = [200.0]
    monkeypatch.setattr(progress_service.time, "time", lambda: fake_now[0])

    write_calls = []
    original_write = progress_service._write_progress_store_unlocked

    def counting_write(now=None):
        write_calls.append(now if now is not None else fake_now[0])
        return original_write(now)

    monkeypatch.setattr(progress_service, "_write_progress_store_unlocked", counting_write)

    progress_service.set_progress("task-1", progress_service.create_progress_entry("https://a", "m4b"))
    progress_service.update_progress_entry("task-1", status="success", percent=100.0)

    assert len(write_calls) == 2
    assert progress_service._progress_store_dirty is False
