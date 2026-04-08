import sqlite3
import sys
import json
from pathlib import Path

import pytest
from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.api.v1 import system as system_api
from core.context import ctx
from core.data.index_runtime_store import activate_generation, allocate_build_generation, ensure_index_runtime_schema
from core.data.index_store import ensure_index_schema
from core.services import cache_service
from core.services import index_build_service
from core.services import index_job_worker
from core.services import index_service
from core.services.card_index_query_service import query_indexed_cards


def _make_test_app():
    app = Flask(__name__)
    app.register_blueprint(system_api.bp)
    return app


def _init_index_db(db_path: Path):
    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        ensure_index_runtime_schema(conn)


class _StopWorkerLoop(Exception):
    pass


def test_rebuild_cards_writes_projection_rows(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    monkeypatch.setattr(index_service, 'DEFAULT_DB_PATH', str(db_path))

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            'CREATE TABLE card_metadata (id TEXT PRIMARY KEY, char_name TEXT, tags TEXT, category TEXT, last_modified REAL, token_count INTEGER, is_favorite INTEGER, has_character_book INTEGER, character_book_name TEXT, description TEXT, first_mes TEXT, mes_example TEXT, creator TEXT, char_version TEXT, file_hash TEXT, file_size INTEGER)'
        )
        conn.execute(
            'INSERT INTO card_metadata (id, char_name, tags, category, last_modified, token_count, is_favorite, has_character_book, character_book_name, description, first_mes, mes_example, creator, char_version, file_hash, file_size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('cards/hero.png', 'Hero', json.dumps(['blue', 'fast']), 'SciFi', 123.0, 4567, 1, 0, '', '', '', '', '', '', '', 0),
        )
        conn.commit()

    monkeypatch.setattr(index_service, 'load_ui_data', lambda: {'cards/hero.png': {'summary': 'pilot note'}}, raising=False)

    index_service.rebuild_card_index()

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            'SELECT entity_type, name, display_category, favorite, summary_preview, token_count FROM index_entities WHERE entity_id = ?',
            ('card::cards/hero.png',),
        ).fetchone()
        tags = conn.execute(
            'SELECT tag FROM index_entity_tags WHERE entity_id = ? ORDER BY tag',
            ('card::cards/hero.png',),
        ).fetchall()

    assert row == ('card', 'Hero', 'SciFi', 1, 'pilot note', 4567)
    assert [tag[0] for tag in tags] == ['blue', 'fast']


def test_rebuild_cards_populates_fulltext_search_index(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    cards_dir = tmp_path / 'cards'
    cards_dir.mkdir()
    monkeypatch.setattr(index_build_service, 'CARDS_FOLDER', str(cards_dir))

    with sqlite3.connect(db_path) as conn:
        ensure_index_runtime_schema(conn)
        conn.execute(
            'CREATE TABLE card_metadata (id TEXT PRIMARY KEY, char_name TEXT, tags TEXT, category TEXT, last_modified REAL, token_count INTEGER, is_favorite INTEGER, has_character_book INTEGER, character_book_name TEXT, description TEXT, first_mes TEXT, mes_example TEXT, creator TEXT, char_version TEXT, file_hash TEXT, file_size INTEGER)'
        )
        conn.execute(
            'INSERT INTO card_metadata (id, char_name, tags, category, last_modified, token_count, is_favorite, has_character_book, character_book_name, description, first_mes, mes_example, creator, char_version, file_hash, file_size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('cards/fulltext.png', 'Fulltext Hero', json.dumps(['rare']), 'SciFi', 123.0, 4567, 0, 0, '', '', '', '', '', '', '', 0),
        )
        conn.commit()

    monkeypatch.setattr(
        index_build_service,
        'load_ui_data',
        lambda: {'cards/fulltext.png': {'summary': 'quoted term pilot entry'}},
        raising=False,
    )

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        generation = allocate_build_generation(conn, 'cards')
        index_build_service.build_cards_generation(conn, generation)
        activate_generation(conn, 'cards', generation, items_written=1)

    result = query_indexed_cards({
        'db_path': str(db_path),
        'search': '"quoted term"',
        'search_mode': 'fulltext',
        'page': 1,
        'page_size': 20,
    })

    assert [item['id'] for item in result['cards']] == ['cards/fulltext.png']


def test_update_card_cache_enqueues_card_upsert(monkeypatch):
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
    monkeypatch.setattr(cache_service, 'extract_card_info', lambda _path: {'data': {'name': 'Hero', 'tags': ['blue']}})
    monkeypatch.setattr(cache_service, 'calculate_token_count', lambda _payload: 111)
    monkeypatch.setattr(cache_service, 'get_wi_meta', lambda _payload: (False, ''))
    monkeypatch.setattr(cache_service, 'enqueue_index_job', lambda *args, **kwargs: calls.append((args, kwargs)), raising=False)

    cache_service.update_card_cache('cards/hero.png', 'D:/cards/hero.png', mtime=123.0)

    assert calls
    assert calls[0][0][0] == 'upsert_card'
    assert calls[0][1]['entity_id'] == 'cards/hero.png'


def test_rebuild_cards_uses_real_card_path_for_source_revision(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    cards_dir = tmp_path / 'cards'
    card_path = cards_dir / 'hero.png'
    cards_dir.mkdir()
    card_path.write_bytes(b'hero')

    monkeypatch.setattr(index_service, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(index_service, 'load_config', lambda: {'cards_dir': str(cards_dir)}, raising=False)

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            'CREATE TABLE card_metadata (id TEXT PRIMARY KEY, char_name TEXT, tags TEXT, category TEXT, last_modified REAL, token_count INTEGER, is_favorite INTEGER, has_character_book INTEGER, character_book_name TEXT, description TEXT, first_mes TEXT, mes_example TEXT, creator TEXT, char_version TEXT, file_hash TEXT, file_size INTEGER)'
        )
        conn.execute(
            'INSERT INTO card_metadata (id, char_name, tags, category, last_modified, token_count, is_favorite, has_character_book, character_book_name, description, first_mes, mes_example, creator, char_version, file_hash, file_size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('hero.png', 'Hero', json.dumps([]), '', 123.0, 4567, 0, 0, '', '', '', '', '', '', '', 0),
        )
        conn.commit()

    monkeypatch.setattr(index_service, 'load_ui_data', lambda: {}, raising=False)

    index_service.rebuild_card_index()

    with sqlite3.connect(db_path) as conn:
        source_revision = conn.execute(
            'SELECT source_revision FROM index_entities WHERE entity_id = ?',
            ('card::hero.png',),
        ).fetchone()[0]

    assert source_revision


def test_rebuild_cards_uses_relative_cards_dir_from_base_dir(monkeypatch, tmp_path):
    db_path = tmp_path / 'data' / 'system' / 'db' / 'cards_metadata.db'
    cards_dir = tmp_path / 'data' / 'library' / 'characters'
    card_path = cards_dir / 'hero.png'
    cards_dir.mkdir(parents=True)
    card_path.write_bytes(b'hero')
    db_path.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(index_service, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(index_service, 'load_config', lambda: {'cards_dir': 'data/library/characters'}, raising=False)

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            'CREATE TABLE card_metadata (id TEXT PRIMARY KEY, char_name TEXT, tags TEXT, category TEXT, last_modified REAL, token_count INTEGER, is_favorite INTEGER, has_character_book INTEGER, character_book_name TEXT, description TEXT, first_mes TEXT, mes_example TEXT, creator TEXT, char_version TEXT, file_hash TEXT, file_size INTEGER)'
        )
        conn.execute(
            'INSERT INTO card_metadata (id, char_name, tags, category, last_modified, token_count, is_favorite, has_character_book, character_book_name, description, first_mes, mes_example, creator, char_version, file_hash, file_size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('hero.png', 'Hero', json.dumps([]), '', 123.0, 4567, 0, 0, '', '', '', '', '', '', '', 0),
        )
        conn.commit()

    monkeypatch.setattr(index_service, 'load_ui_data', lambda: {}, raising=False)

    index_service.rebuild_card_index()

    with sqlite3.connect(db_path) as conn:
        source_path, source_revision = conn.execute(
            'SELECT source_path, source_revision FROM index_entities WHERE entity_id = ?',
            ('card::hero.png',),
        ).fetchone()

    assert source_path == str(card_path)
    assert source_revision


def test_index_status_endpoint_returns_runtime_snapshot(monkeypatch):
    status_snapshot = {
        'schema': {'state': 'ready', 'message': 'bootstrap', 'db_version': 1, 'index_runtime_version': 1},
        'cards': {'state': 'building', 'phase': 'build_entities', 'active_generation': 1, 'building_generation': 2, 'items_written': 42, 'last_error': ''},
        'worldinfo': {'state': 'ready', 'phase': 'ready', 'active_generation': 3, 'building_generation': 0, 'items_written': 10, 'last_error': ''},
        'jobs': {'pending_jobs': 3, 'worker_state': 'processing'},
        'state': 'building',
        'scope': 'cards',
        'progress': 42,
        'message': 'bootstrap',
        'pending_jobs': 3,
    }
    monkeypatch.setattr(system_api, 'get_index_status', lambda: status_snapshot)

    client = _make_test_app().test_client()
    response = client.get('/api/index/status')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['status']['cards']['state'] == 'building'
    assert payload['status']['jobs']['pending_jobs'] == 3


def test_get_index_status_returns_detached_nested_snapshot():
    original = {
        'schema': {'state': 'ready', 'message': 'ok', 'db_version': 1, 'index_runtime_version': 1},
        'cards': {'state': 'building', 'phase': 'build_entities', 'active_generation': 1, 'building_generation': 2, 'items_written': 5, 'last_error': ''},
        'worldinfo': {'state': 'ready', 'phase': 'ready', 'active_generation': 3, 'building_generation': 0, 'items_written': 4, 'last_error': ''},
        'jobs': {'pending_jobs': 2, 'worker_state': 'processing'},
        'state': 'building',
        'scope': 'cards',
        'progress': 10,
        'message': 'bootstrap',
        'pending_jobs': 2,
    }
    ctx.index_state.clear()
    ctx.index_state.update(original)

    snapshot = index_service.get_index_status()
    snapshot['jobs']['pending_jobs'] = 99
    snapshot['cards']['state'] = 'failed'
    snapshot['schema']['message'] = 'mutated'

    assert ctx.index_state['jobs']['pending_jobs'] == 2
    assert ctx.index_state['cards']['state'] == 'building'
    assert ctx.index_state['schema']['message'] == 'bootstrap'


def test_get_index_status_reads_persisted_runtime_build_state(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    monkeypatch.setattr(index_service, 'DEFAULT_DB_PATH', str(db_path))

    with sqlite3.connect(db_path) as conn:
        ensure_index_runtime_schema(conn)
        conn.execute(
            "UPDATE index_build_state SET active_generation = 2, building_generation = 0, state = 'ready', phase = 'ready', items_written = 11 WHERE scope = 'cards'"
        )
        conn.execute(
            "UPDATE index_build_state SET active_generation = 3, building_generation = 0, state = 'ready', phase = 'ready', items_written = 7 WHERE scope = 'worldinfo'"
        )
        conn.execute(
            "UPDATE index_schema_state SET applied_version = 1, state = 'ready' WHERE component = 'db'"
        )
        conn.execute(
            "UPDATE index_schema_state SET applied_version = 1, state = 'ready' WHERE component = 'index_runtime'"
        )
        conn.commit()

    ctx.index_state.clear()
    ctx.index_state.update(type(ctx.index_state)())

    snapshot = index_service.get_index_status()

    assert snapshot['schema']['state'] == 'ready'
    assert snapshot['schema']['db_version'] == 1
    assert snapshot['schema']['index_runtime_version'] == 1
    assert snapshot['state'] == 'ready'
    assert snapshot['scope'] == 'cards'
    assert snapshot['message'] == ''
    assert snapshot['pending_jobs'] == 0
    assert snapshot['cards']['state'] == 'ready'
    assert snapshot['cards']['active_generation'] == 2
    assert snapshot['cards']['items_written'] == 11
    assert snapshot['worldinfo']['state'] == 'ready'
    assert snapshot['worldinfo']['active_generation'] == 3
    assert snapshot['worldinfo']['items_written'] == 7


def test_index_rebuild_endpoint_enqueues_scope(monkeypatch):
    captured = {}

    def fake_request_index_rebuild(scope='cards'):
        captured['scope'] = scope

    monkeypatch.setattr(system_api, 'request_index_rebuild', fake_request_index_rebuild)

    client = _make_test_app().test_client()
    response = client.post('/api/index/rebuild', json={'scope': 'cards'})

    assert response.status_code == 200
    assert response.get_json()['success'] is True
    assert captured['scope'] == 'cards'


def test_index_rebuild_endpoint_rejects_unsupported_scope():
    client = _make_test_app().test_client()

    response = client.post('/api/index/rebuild', json={'scope': 'files'})

    assert response.status_code == 400
    assert response.get_json()['success'] is False


def test_worker_loop_marks_bad_job_failed_and_continues(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    _init_index_db(db_path)
    monkeypatch.setattr(index_job_worker, 'DEFAULT_DB_PATH', str(db_path))

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO index_jobs(job_type, payload_json) VALUES (?, ?)',
            ('rebuild_scope', '{bad json'),
        )
        conn.execute(
            'INSERT INTO index_jobs(job_type, payload_json) VALUES (?, ?)',
            ('rebuild_scope', '{"scope": "cards"}'),
        )
        conn.commit()

    calls = []

    def fake_rebuild_scope_generation(scope='cards', reason='bootstrap'):
        calls.append((scope, reason))

    wait_calls = {'count': 0}

    def fake_wait(timeout):
        wait_calls['count'] += 1
        if wait_calls['count'] >= 2:
            raise _StopWorkerLoop()
        return True

    monkeypatch.setattr(index_job_worker, 'rebuild_scope_generation', fake_rebuild_scope_generation)
    monkeypatch.setattr(ctx.index_wakeup, 'wait', fake_wait)
    ctx.index_state.update({'state': 'empty', 'scope': 'cards', 'progress': 0, 'message': '', 'pending_jobs': 0})
    ctx.index_wakeup.set()

    with pytest.raises(_StopWorkerLoop):
        index_job_worker.worker_loop()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            'SELECT id, status, error_msg FROM index_jobs ORDER BY id'
        ).fetchall()

    assert [row[1] for row in rows] == ['failed', 'done']
    assert rows[0][2]
    assert calls == [('cards', 'manual_rebuild')]


def test_worker_loop_processes_upsert_card_job(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    cards_dir = tmp_path / 'cards'
    card_path = cards_dir / 'hero.png'
    cards_dir.mkdir()
    card_path.write_bytes(b'hero')

    monkeypatch.setattr(index_job_worker, 'DEFAULT_DB_PATH', str(db_path))

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            'CREATE TABLE card_metadata (id TEXT PRIMARY KEY, char_name TEXT, tags TEXT, category TEXT, last_modified REAL, token_count INTEGER, is_favorite INTEGER, has_character_book INTEGER, character_book_name TEXT, description TEXT, first_mes TEXT, mes_example TEXT, creator TEXT, char_version TEXT, file_hash TEXT, file_size INTEGER)'
        )
        conn.execute(
            'INSERT INTO card_metadata (id, char_name, tags, category, last_modified, token_count, is_favorite, has_character_book, character_book_name, description, first_mes, mes_example, creator, char_version, file_hash, file_size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('hero.png', 'Hero', json.dumps(['blue']), 'SciFi', 123.0, 4567, 1, 0, '', '', '', '', '', '', '', 0),
        )
        conn.execute(
            'INSERT INTO index_jobs(job_type, entity_id, source_path, payload_json) VALUES (?, ?, ?, ?)',
            ('upsert_card', 'hero.png', str(card_path), '{}'),
        )
        conn.commit()

    calls = []

    def fake_rebuild_scope_generation(scope='cards', reason='bootstrap'):
        calls.append((scope, reason))

    wait_calls = {'count': 0}

    def fake_wait(timeout):
        wait_calls['count'] += 1
        if wait_calls['count'] >= 2:
            raise _StopWorkerLoop()
        return True

    monkeypatch.setattr(index_job_worker, 'rebuild_scope_generation', fake_rebuild_scope_generation)
    monkeypatch.setattr(ctx.index_wakeup, 'wait', fake_wait)
    ctx.index_state.update({'state': 'empty', 'scope': 'cards', 'progress': 0, 'message': '', 'pending_jobs': 0})
    ctx.index_wakeup.set()

    with pytest.raises(_StopWorkerLoop):
        index_job_worker.worker_loop()

    with sqlite3.connect(db_path) as conn:
        job_row = conn.execute(
            'SELECT status, error_msg FROM index_jobs WHERE job_type = ?',
            ('upsert_card',),
        ).fetchone()

    assert job_row == ('done', '')
    assert calls == [('cards', 'incremental_reconcile')]


def test_worker_loop_coalesces_multiple_worldinfo_reconcile_jobs(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    _init_index_db(db_path)
    monkeypatch.setattr(index_job_worker, 'DEFAULT_DB_PATH', str(db_path))

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO index_jobs(job_type, source_path, payload_json) VALUES (?, ?, ?)',
            ('upsert_worldinfo_path', 'D:/data/lorebooks/a.json', '{}'),
        )
        conn.execute(
            'INSERT INTO index_jobs(job_type, entity_id, payload_json) VALUES (?, ?, ?)',
            ('upsert_world_embedded', 'card::hero.png', '{}'),
        )
        conn.execute(
            'INSERT INTO index_jobs(job_type, entity_id, payload_json) VALUES (?, ?, ?)',
            ('upsert_world_owner', 'hero.png', '{}'),
        )
        conn.commit()

    calls = []

    def fake_rebuild_scope_generation(scope='cards', reason='bootstrap'):
        calls.append((scope, reason))

    wait_calls = {'count': 0}

    def fake_wait(timeout):
        wait_calls['count'] += 1
        if wait_calls['count'] >= 2:
            raise _StopWorkerLoop()
        return True

    monkeypatch.setattr(index_job_worker, 'rebuild_scope_generation', fake_rebuild_scope_generation)
    monkeypatch.setattr(ctx.index_wakeup, 'wait', fake_wait)
    ctx.index_state.update({'state': 'empty', 'scope': 'cards', 'progress': 0, 'message': '', 'pending_jobs': 0})
    ctx.index_wakeup.set()

    with pytest.raises(_StopWorkerLoop):
        index_job_worker.worker_loop()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            'SELECT job_type, status, error_msg FROM index_jobs ORDER BY id'
        ).fetchall()

    assert [row[1] for row in rows] == ['done', 'done', 'done']
    assert calls == [('worldinfo', 'incremental_reconcile')]


def test_worker_loop_updates_worldinfo_path_in_active_generation_without_full_rebuild(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    lore_dir = tmp_path / 'lorebooks'
    lore_dir.mkdir()
    book_path = lore_dir / 'dragon.json'
    book_path.write_text(json.dumps({'name': 'Dragon Lore', 'entries': {}}, ensure_ascii=False), encoding='utf-8')

    _init_index_db(db_path)
    monkeypatch.setattr(index_job_worker, 'DEFAULT_DB_PATH', str(db_path))

    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE index_build_state SET active_generation = 1, state = 'ready', phase = 'ready' WHERE scope = 'worldinfo'")
        conn.execute(
            "INSERT OR REPLACE INTO index_entities_v2(generation, entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 'world::global::dragon.json', 'world_global', str(book_path), '', 'Old Lore', 'dragon.json', '', '', 'physical', 0, '', 10.0, 0.0, 0, 'old lore', 10.0, '', '10:1'),
        )
        conn.execute(
            'INSERT INTO index_jobs(job_type, source_path, payload_json) VALUES (?, ?, ?)',
            ('upsert_worldinfo_path', str(book_path), '{}'),
        )
        conn.commit()

    calls = []

    def fake_rebuild_scope_generation(scope='cards', reason='bootstrap'):
        calls.append((scope, reason))

    wait_calls = {'count': 0}

    def fake_wait(timeout):
        wait_calls['count'] += 1
        if wait_calls['count'] >= 2:
            raise _StopWorkerLoop()
        return True

    monkeypatch.setattr(index_job_worker, 'rebuild_scope_generation', fake_rebuild_scope_generation)
    monkeypatch.setattr(index_build_service, 'load_config', lambda: {'world_info_dir': str(lore_dir), 'resources_dir': str(tmp_path / 'resources')})
    monkeypatch.setattr(index_build_service, 'load_ui_data', lambda: {'_resource_item_categories_v1': {'worldinfo': {}}})
    monkeypatch.setattr(ctx.index_wakeup, 'wait', fake_wait)
    ctx.index_state.update({'state': 'empty', 'scope': 'cards', 'progress': 0, 'message': '', 'pending_jobs': 0})
    ctx.index_wakeup.set()

    with pytest.raises(_StopWorkerLoop):
        index_job_worker.worker_loop()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT generation, entity_id, name, display_category FROM index_entities_v2 WHERE generation = 1 AND entity_type LIKE 'world_%' ORDER BY entity_id"
        ).fetchall()
        stats = conn.execute(
            "SELECT entity_type, category_path, direct_count, subtree_count FROM index_category_stats_v2 WHERE generation = 1 AND scope = 'worldinfo' ORDER BY entity_type, category_path"
        ).fetchall()
        job_row = conn.execute(
            'SELECT status, error_msg FROM index_jobs WHERE job_type = ?',
            ('upsert_worldinfo_path',),
        ).fetchone()

    assert rows == [(1, 'world::global::dragon.json', 'Dragon Lore', '')]
    assert stats == []
    assert job_row == ('done', '')
    assert calls == []


def test_worker_loop_updates_embedded_worldinfo_in_active_generation_without_full_rebuild(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    cards_dir = tmp_path / 'cards'
    cards_dir.mkdir()
    card_path = cards_dir / 'hero.png'
    card_path.write_bytes(b'hero')

    _init_index_db(db_path)
    monkeypatch.setattr(index_job_worker, 'DEFAULT_DB_PATH', str(db_path))

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'CREATE TABLE card_metadata (id TEXT PRIMARY KEY, char_name TEXT, category TEXT, last_modified REAL, has_character_book INTEGER, character_book_name TEXT)'
        )
        conn.execute(
            'INSERT INTO card_metadata (id, char_name, category, last_modified, has_character_book, character_book_name) VALUES (?, ?, ?, ?, ?, ?)',
            ('hero.png', 'Hero', 'fantasy', 12.0, 1, 'Old Embedded'),
        )
        conn.execute("UPDATE index_build_state SET active_generation = 1, state = 'ready', phase = 'ready' WHERE scope = 'worldinfo'")
        conn.execute(
            "INSERT OR REPLACE INTO index_entities_v2(generation, entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 'world::embedded::hero.png', 'world_embedded', str(card_path), 'card::hero.png', 'Old Embedded', 'hero.png', 'fantasy', '', 'inherited', 0, '', 10.0, 0.0, 0, 'old embedded', 10.0, '', '10:1'),
        )
        conn.execute(
            'INSERT INTO index_jobs(job_type, entity_id, source_path, payload_json) VALUES (?, ?, ?, ?)',
            ('upsert_world_embedded', 'hero.png', str(card_path), '{}'),
        )
        conn.commit()

    calls = []

    def fake_rebuild_scope_generation(scope='cards', reason='bootstrap'):
        calls.append((scope, reason))

    wait_calls = {'count': 0}

    def fake_wait(timeout):
        wait_calls['count'] += 1
        if wait_calls['count'] >= 2:
            raise _StopWorkerLoop()
        return True

    monkeypatch.setattr(index_job_worker, 'rebuild_scope_generation', fake_rebuild_scope_generation)
    monkeypatch.setattr(index_build_service, 'CARDS_FOLDER', str(cards_dir))
    monkeypatch.setattr(index_build_service, 'extract_card_info', lambda _path: {'data': {'character_book': {'name': 'New Embedded', 'entries': {'0': {'content': 'hello'}}}}})
    monkeypatch.setattr(index_build_service, 'load_ui_data', lambda: {'hero.png': {'summary': 'embedded summary'}})
    monkeypatch.setattr(ctx.index_wakeup, 'wait', fake_wait)
    ctx.index_state.update({'state': 'empty', 'scope': 'cards', 'progress': 0, 'message': '', 'pending_jobs': 0})
    ctx.index_wakeup.set()

    with pytest.raises(_StopWorkerLoop):
        index_job_worker.worker_loop()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT generation, entity_id, name, summary_preview FROM index_entities_v2 WHERE generation = 1 AND entity_type = 'world_embedded' ORDER BY entity_id"
        ).fetchall()
        stats = conn.execute(
            "SELECT entity_type, category_path, direct_count, subtree_count FROM index_category_stats_v2 WHERE generation = 1 AND scope = 'worldinfo' ORDER BY entity_type, category_path"
        ).fetchall()
        job_row = conn.execute(
            'SELECT status, error_msg FROM index_jobs WHERE job_type = ?',
            ('upsert_world_embedded',),
        ).fetchone()

    assert rows == [(1, 'world::embedded::hero.png', 'New Embedded', 'embedded summary')]
    assert stats == [('world_all', 'fantasy', 1, 1), ('world_embedded', 'fantasy', 1, 1)]
    assert job_row == ('done', '')
    assert calls == []


def test_worker_loop_updates_owner_worldinfo_in_active_generation_without_full_rebuild(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    cards_dir = tmp_path / 'cards'
    resources_dir = tmp_path / 'resources'
    cards_dir.mkdir()
    card_path = cards_dir / 'hero.png'
    card_path.write_bytes(b'hero')
    lore_dir = resources_dir / 'hero-assets' / 'lorebooks'
    lore_dir.mkdir(parents=True)
    resource_book = lore_dir / 'resource-book.json'
    resource_book.write_text(json.dumps({'name': 'Resource Book', 'entries': {}}, ensure_ascii=False), encoding='utf-8')

    _init_index_db(db_path)
    monkeypatch.setattr(index_job_worker, 'DEFAULT_DB_PATH', str(db_path))

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'CREATE TABLE card_metadata (id TEXT PRIMARY KEY, char_name TEXT, category TEXT, last_modified REAL, has_character_book INTEGER, character_book_name TEXT)'
        )
        conn.execute(
            'INSERT INTO card_metadata (id, char_name, category, last_modified, has_character_book, character_book_name) VALUES (?, ?, ?, ?, ?, ?)',
            ('hero.png', 'Hero', 'fantasy', 12.0, 1, 'Old Embedded'),
        )
        conn.execute("UPDATE index_build_state SET active_generation = 1, state = 'ready', phase = 'ready' WHERE scope = 'worldinfo'")
        conn.execute(
            "INSERT OR REPLACE INTO index_entities_v2(generation, entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 'world::embedded::hero.png', 'world_embedded', str(card_path), 'card::hero.png', 'Old Embedded', 'hero.png', 'fantasy', '', 'inherited', 0, '', 10.0, 0.0, 0, 'old embedded', 10.0, '', '10:1'),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_entities_v2(generation, entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 'world::resource::hero.png::resource-book.json', str('world_resource'), str(resource_book), 'card::hero.png', 'Old Resource', 'resource-book.json', 'old-cat', '', 'inherited', 0, '', 10.0, 0.0, 0, 'old resource', 10.0, '', '10:1'),
        )
        conn.execute(
            'INSERT INTO index_jobs(job_type, entity_id, source_path, payload_json) VALUES (?, ?, ?, ?)',
            ('upsert_world_owner', 'hero.png', str(card_path), '{}'),
        )
        conn.commit()

    calls = []

    def fake_rebuild_scope_generation(scope='cards', reason='bootstrap'):
        calls.append((scope, reason))

    wait_calls = {'count': 0}

    def fake_wait(timeout):
        wait_calls['count'] += 1
        if wait_calls['count'] >= 2:
            raise _StopWorkerLoop()
        return True

    monkeypatch.setattr(index_job_worker, 'rebuild_scope_generation', fake_rebuild_scope_generation)
    monkeypatch.setattr(index_build_service, 'CARDS_FOLDER', str(cards_dir))
    monkeypatch.setattr(index_build_service, 'load_config', lambda: {'world_info_dir': str(tmp_path / 'global-lorebooks'), 'resources_dir': str(resources_dir)})
    monkeypatch.setattr(index_build_service, 'extract_card_info', lambda _path: {'data': {'character_book': {'name': 'New Embedded', 'entries': {'0': {'content': 'hello'}}}}})
    monkeypatch.setattr(index_build_service, 'load_ui_data', lambda: {
        'hero.png': {'resource_folder': 'hero-assets', 'summary': 'embedded summary'},
        '_resource_item_categories_v1': {
            'worldinfo': {
                str(resource_book).replace('\\', '/').lower(): {'category': 'override-cat', 'updated_at': 1}
            }
        },
    })
    monkeypatch.setattr(ctx.index_wakeup, 'wait', fake_wait)
    ctx.index_state.update({'state': 'empty', 'scope': 'cards', 'progress': 0, 'message': '', 'pending_jobs': 0})
    ctx.index_wakeup.set()

    with pytest.raises(_StopWorkerLoop):
        index_job_worker.worker_loop()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT generation, entity_id, entity_type, name, display_category, summary_preview FROM index_entities_v2 WHERE generation = 1 AND entity_type LIKE 'world_%' ORDER BY entity_id"
        ).fetchall()
        stats = conn.execute(
            "SELECT entity_type, category_path, direct_count, subtree_count FROM index_category_stats_v2 WHERE generation = 1 AND scope = 'worldinfo' ORDER BY entity_type, category_path"
        ).fetchall()
        job_row = conn.execute(
            'SELECT status, error_msg FROM index_jobs WHERE job_type = ?',
            ('upsert_world_owner',),
        ).fetchone()

    assert rows == [
        (1, 'world::embedded::hero.png', 'world_embedded', 'New Embedded', 'fantasy', 'embedded summary'),
        (1, 'world::resource::hero.png::resource-book.json', 'world_resource', 'Resource Book', 'override-cat', ''),
    ]
    assert stats == [
        ('world_all', 'fantasy', 1, 1),
        ('world_all', 'override-cat', 1, 1),
        ('world_embedded', 'fantasy', 1, 1),
        ('world_resource', 'override-cat', 1, 1),
    ]
    assert job_row == ('done', '')
    assert calls == []


def test_worker_loop_marks_unknown_job_failed(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    _init_index_db(db_path)
    monkeypatch.setattr(index_job_worker, 'DEFAULT_DB_PATH', str(db_path))

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO index_jobs(job_type, payload_json) VALUES (?, ?)',
            ('mystery_job', '{}'),
        )
        conn.commit()

    wait_calls = {'count': 0}

    def fake_wait(timeout):
        wait_calls['count'] += 1
        if wait_calls['count'] >= 2:
            raise _StopWorkerLoop()
        return True

    monkeypatch.setattr(ctx.index_wakeup, 'wait', fake_wait)
    ctx.index_state.update({'state': 'empty', 'scope': 'cards', 'progress': 0, 'message': '', 'pending_jobs': 0})
    ctx.index_wakeup.set()

    with pytest.raises(_StopWorkerLoop):
        index_job_worker.worker_loop()

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            'SELECT status, error_msg FROM index_jobs WHERE job_type = ?',
            ('mystery_job',),
        ).fetchone()

    assert row[0] == 'failed'
    assert 'unsupported index job type' in row[1]
