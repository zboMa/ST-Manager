import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.services import cache_service
from core.services import scan_service


def test_worldinfo_watch_filter_accepts_global_and_resource_lorebooks(monkeypatch):
    monkeypatch.setattr(scan_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})

    assert scan_service._is_worldinfo_watch_path('D:/data/lorebooks/main/book.json') is True
    assert scan_service._is_worldinfo_watch_path('D:/data/resources/lucy/lorebooks/book.json') is True
    assert scan_service._is_worldinfo_watch_path('D:/data/resources/lucy/images/cover.png') is False


def test_update_card_cache_enqueues_embedded_owner_refresh(monkeypatch):
    calls = []

    class _FakeConn:
        def cursor(self):
            return self

        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return {'is_favorite': 0, 'has_character_book': 0}

        def commit(self):
            return None

    monkeypatch.setattr(cache_service, 'get_db', lambda: _FakeConn())
    monkeypatch.setattr(cache_service, 'get_file_hash_and_size', lambda _path: ('h', 12))
    monkeypatch.setattr(cache_service, 'extract_card_info', lambda _path: {'data': {'name': 'Hero', 'tags': [], 'character_book': {'name': 'Book', 'entries': {}}}})
    monkeypatch.setattr(cache_service, 'calculate_token_count', lambda _payload: 111)
    monkeypatch.setattr(cache_service, 'get_wi_meta', lambda _payload: (True, 'Book'))
    monkeypatch.setattr(cache_service, 'enqueue_index_job', lambda *args, **kwargs: calls.append((args, kwargs)))

    cache_service.update_card_cache('cards/hero.png', 'D:/cards/hero.png', mtime=123.0)

    job_names = [call[0][0] for call in calls]
    assert 'upsert_card' in job_names
    assert 'upsert_world_embedded' in job_names


def test_update_card_cache_enqueues_embedded_owner_refresh_when_worldinfo_removed(monkeypatch):
    calls = []

    class _FakeConn:
        def cursor(self):
            return self

        def execute(self, query, *_args, **_kwargs):
            self._last_query = query
            return self

        def fetchone(self):
            if 'SELECT is_favorite, has_character_book' in getattr(self, '_last_query', ''):
                return {'is_favorite': 0, 'has_character_book': 1}
            return {'is_favorite': 0}

        def commit(self):
            return None

    monkeypatch.setattr(cache_service, 'get_db', lambda: _FakeConn())
    monkeypatch.setattr(cache_service, 'get_file_hash_and_size', lambda _path: ('h', 12))
    monkeypatch.setattr(cache_service, 'extract_card_info', lambda _path: {'data': {'name': 'Hero', 'tags': []}})
    monkeypatch.setattr(cache_service, 'calculate_token_count', lambda _payload: 111)
    monkeypatch.setattr(cache_service, 'get_wi_meta', lambda _payload: (False, ''))
    monkeypatch.setattr(cache_service, 'enqueue_index_job', lambda *args, **kwargs: calls.append((args, kwargs)))

    cache_service.update_card_cache('cards/hero.png', 'D:/cards/hero.png', mtime=123.0)

    job_names = [call[0][0] for call in calls]
    assert 'upsert_card' in job_names
    assert 'upsert_world_embedded' in job_names


def test_worldinfo_watch_filter_rejects_sibling_prefix_paths(monkeypatch):
    monkeypatch.setattr(scan_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})

    assert scan_service._is_worldinfo_watch_path('D:/data/lorebooks2/x.json') is False


def test_worldinfo_watch_filter_is_case_tolerant_for_valid_paths(monkeypatch):
    monkeypatch.setattr(scan_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})

    assert scan_service._is_worldinfo_watch_path('d:/DATA/LOREBOOKS/main/book.JSON') is True
    assert scan_service._is_worldinfo_watch_path('d:/DATA/RESOURCES/lucy/LOREBOOKS/book.JSON') is True


def test_worldinfo_watcher_move_into_lorebook_path_enqueues_dest_path(monkeypatch):
    calls = []
    scheduled = {}

    class _FakeObserver:
        daemon = False

        def schedule(self, handler, watch_path, recursive=True):
            scheduled['handler'] = handler
            scheduled['watch_path'] = watch_path
            scheduled['recursive'] = recursive

        def start(self):
            scheduled['started'] = True

    class _FakeHandlerBase:
        pass

    monkeypatch.setattr(scan_service.ctx, 'should_ignore_fs_event', lambda: False)
    monkeypatch.setattr(scan_service, 'CARDS_FOLDER', 'D:/cards')
    monkeypatch.setattr(scan_service, 'enqueue_index_job', lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(scan_service, 'request_scan', lambda **_kwargs: calls.append((('scan',), {})))

    watchdog_module = types.ModuleType('watchdog')
    observers_module = types.ModuleType('watchdog.observers')
    observers_module.Observer = _FakeObserver
    events_module = types.ModuleType('watchdog.events')
    events_module.FileSystemEventHandler = _FakeHandlerBase

    monkeypatch.setitem(sys.modules, 'watchdog', watchdog_module)
    monkeypatch.setitem(sys.modules, 'watchdog.observers', observers_module)
    monkeypatch.setitem(sys.modules, 'watchdog.events', events_module)

    monkeypatch.setattr(scan_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})

    scan_service.start_fs_watcher()

    event = types.SimpleNamespace(
        is_directory=False,
        event_type='moved',
        src_path='D:/tmp/book.json',
        dest_path='D:/data/lorebooks/main/book.json',
    )
    scheduled['handler'].on_any_event(event)

    assert calls == [(('upsert_worldinfo_path',), {'source_path': 'D:/data/lorebooks/main/book.json'})]


def test_update_card_cache_returns_false_when_cache_write_fails(monkeypatch):
    monkeypatch.setattr(cache_service, 'get_db', lambda: (_ for _ in ()).throw(RuntimeError('db down')))

    assert cache_service.update_card_cache('cards/hero.png', 'D:/cards/hero.png', mtime=123.0) is False


def test_cards_api_worldinfo_owner_enqueue_is_gated_by_update_card_cache_success_contract():
    source = (ROOT / 'core/api/v1/cards.py').read_text(encoding='utf-8')

    assert "cache_updated = update_card_cache(final_rel_path_id, current_full_path, parsed_info=info, mtime=current_mtime)" in source
    assert "if cache_updated:\n            enqueue_index_job('upsert_world_owner', entity_id=final_rel_path_id, source_path=current_full_path)" in source
    assert "update_card_cache(final_rel_path_id, current_full_path, parsed_info=info, mtime=current_mtime)\n        enqueue_index_job('upsert_world_owner', entity_id=final_rel_path_id, source_path=current_full_path)" not in source


def test_background_scanner_enqueues_cards_and_worldinfo_rebuilds_when_changes_detected(monkeypatch):
    calls = []

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *_args, **_kwargs):
            return None

        def cursor(self):
            return self

        def fetchall(self):
            return [('gone.png', 10.0, 100, 0, 'hash', 0)]

        def commit(self):
            return None

    monkeypatch.setattr(scan_service.sqlite3, 'connect', lambda *_args, **_kwargs: _FakeConn())
    monkeypatch.setattr(scan_service, 'CARDS_FOLDER', 'D:/cards')
    monkeypatch.setattr(scan_service, 'enqueue_index_job', lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(scan_service, 'schedule_reload', lambda **_kwargs: None)
    monkeypatch.setattr(scan_service.os, 'walk', lambda _root: iter([('D:/cards', [], [])]))

    scan_service._perform_scan_logic()

    assert calls == [
        (('rebuild_scope',), {'payload': {'scope': 'cards'}}),
        (('rebuild_scope',), {'payload': {'scope': 'worldinfo'}}),
    ]


def test_update_card_cache_returns_true_when_enqueue_fails_after_commit(monkeypatch):
    calls = []

    class _FakeConn:
        def cursor(self):
            return self

        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return {'is_favorite': 0, 'has_character_book': 0}

        def commit(self):
            calls.append('commit')
            return None

    monkeypatch.setattr(cache_service, 'get_db', lambda: _FakeConn())
    monkeypatch.setattr(cache_service, 'get_file_hash_and_size', lambda _path: ('h', 12))
    monkeypatch.setattr(cache_service, 'extract_card_info', lambda _path: {'data': {'name': 'Hero', 'tags': [], 'character_book': {'name': 'Book', 'entries': {}}}})
    monkeypatch.setattr(cache_service, 'calculate_token_count', lambda _payload: 111)
    monkeypatch.setattr(cache_service, 'get_wi_meta', lambda _payload: (True, 'Book'))

    def _boom(*_args, **_kwargs):
        raise RuntimeError('queue down')

    monkeypatch.setattr(cache_service, 'enqueue_index_job', _boom)

    assert cache_service.update_card_cache('cards/hero.png', 'D:/cards/hero.png', mtime=123.0) is True
    assert calls == ['commit']


def test_worldinfo_watch_filter_returns_false_for_cross_drive_path(monkeypatch):
    monkeypatch.setattr(scan_service, 'load_config', lambda: {'world_info_dir': 'D:/data/lorebooks', 'resources_dir': 'D:/data/resources'})

    assert scan_service._is_worldinfo_watch_path('E:/other/book.json') is False


def test_start_fs_watcher_schedules_cards_and_distinct_worldinfo_roots(monkeypatch):
    scheduled = []

    class _FakeObserver:
        daemon = False

        def schedule(self, handler, watch_path, recursive=True):
            scheduled.append((handler, watch_path, recursive))

        def start(self):
            return None

    class _FakeHandlerBase:
        pass

    watchdog_module = types.ModuleType('watchdog')
    observers_module = types.ModuleType('watchdog.observers')
    observers_module.Observer = _FakeObserver
    events_module = types.ModuleType('watchdog.events')
    events_module.FileSystemEventHandler = _FakeHandlerBase

    monkeypatch.setitem(sys.modules, 'watchdog', watchdog_module)
    monkeypatch.setitem(sys.modules, 'watchdog.observers', observers_module)
    monkeypatch.setitem(sys.modules, 'watchdog.events', events_module)
    monkeypatch.setattr(scan_service, 'CARDS_FOLDER', 'D:/cards')
    monkeypatch.setattr(scan_service, 'load_config', lambda: {
        'world_info_dir': 'D:/data/lorebooks',
        'resources_dir': 'D:/data/resources',
    })

    scan_service.start_fs_watcher()

    assert [item[1] for item in scheduled] == ['D:/cards', 'D:/data/lorebooks', 'D:/data/resources']
    assert all(item[2] is True for item in scheduled)
