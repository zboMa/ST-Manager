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
from core.data.index_store import ensure_index_schema
from core.services import cache_service
from core.services import index_service
from core.services.card_index_query_service import query_indexed_cards


def _make_test_app():
    app = Flask(__name__)
    app.register_blueprint(system_api.bp)
    return app


def _init_index_db(db_path: Path):
    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)


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
    monkeypatch.setattr(index_service, 'DEFAULT_DB_PATH', str(db_path))

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            'CREATE TABLE card_metadata (id TEXT PRIMARY KEY, char_name TEXT, tags TEXT, category TEXT, last_modified REAL, token_count INTEGER, is_favorite INTEGER, has_character_book INTEGER, character_book_name TEXT, description TEXT, first_mes TEXT, mes_example TEXT, creator TEXT, char_version TEXT, file_hash TEXT, file_size INTEGER)'
        )
        conn.execute(
            'INSERT INTO card_metadata (id, char_name, tags, category, last_modified, token_count, is_favorite, has_character_book, character_book_name, description, first_mes, mes_example, creator, char_version, file_hash, file_size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('cards/fulltext.png', 'Fulltext Hero', json.dumps(['rare']), 'SciFi', 123.0, 4567, 0, 0, '', '', '', '', '', '', '', 0),
        )
        conn.commit()

    monkeypatch.setattr(
        index_service,
        'load_ui_data',
        lambda: {'cards/fulltext.png': {'summary': 'quoted term pilot entry'}},
        raising=False,
    )

    index_service.rebuild_card_index()

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
    assert payload['status']['state'] == 'building'
    assert payload['status']['pending_jobs'] == 3


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
    monkeypatch.setattr(index_service, 'DEFAULT_DB_PATH', str(db_path))

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

    def fake_rebuild_card_index(scope='cards'):
        calls.append(scope)

    sleep_calls = {'count': 0}

    def fake_sleep(_seconds):
        sleep_calls['count'] += 1
        if sleep_calls['count'] >= 3:
            raise _StopWorkerLoop()

    monkeypatch.setattr(index_service, 'rebuild_card_index', fake_rebuild_card_index)
    monkeypatch.setattr(index_service.time, 'sleep', fake_sleep)
    ctx.index_state.update({'state': 'empty', 'scope': 'cards', 'progress': 0, 'message': '', 'pending_jobs': 0})

    with pytest.raises(_StopWorkerLoop):
        index_service._worker_loop()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            'SELECT id, status, error_msg FROM index_jobs ORDER BY id'
        ).fetchall()

    assert [row[1] for row in rows] == ['failed', 'done']
    assert rows[0][2]
    assert calls == ['cards']
    assert index_service.get_index_status()['state'] == 'ready'


def test_worker_loop_processes_upsert_card_job(monkeypatch, tmp_path):
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
            ('hero.png', 'Hero', json.dumps(['blue']), 'SciFi', 123.0, 4567, 1, 0, '', '', '', '', '', '', '', 0),
        )
        conn.execute(
            'INSERT INTO index_jobs(job_type, entity_id, source_path, payload_json) VALUES (?, ?, ?, ?)',
            ('upsert_card', 'hero.png', str(card_path), '{}'),
        )
        conn.commit()

    monkeypatch.setattr(index_service, 'load_ui_data', lambda: {'hero.png': {'summary': 'pilot note'}}, raising=False)

    sleep_calls = {'count': 0}

    def fake_sleep(_seconds):
        sleep_calls['count'] += 1
        if sleep_calls['count'] >= 3:
            raise _StopWorkerLoop()

    monkeypatch.setattr(index_service.time, 'sleep', fake_sleep)
    ctx.index_state.update({'state': 'empty', 'scope': 'cards', 'progress': 0, 'message': '', 'pending_jobs': 0})

    with pytest.raises(_StopWorkerLoop):
        index_service._worker_loop()

    with sqlite3.connect(db_path) as conn:
        job_row = conn.execute(
            'SELECT status, error_msg FROM index_jobs WHERE job_type = ?',
            ('upsert_card',),
        ).fetchone()
        entity_row = conn.execute(
            'SELECT name, display_category, favorite, summary_preview FROM index_entities WHERE entity_id = ?',
            ('card::hero.png',),
        ).fetchone()
        tags = conn.execute(
            'SELECT tag FROM index_entity_tags WHERE entity_id = ? ORDER BY tag',
            ('card::hero.png',),
        ).fetchall()

    assert job_row == ('done', '')
    assert entity_row == ('Hero', 'SciFi', 1, 'pilot note')
    assert [tag[0] for tag in tags] == ['blue']


def test_worker_loop_marks_unknown_job_failed(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    _init_index_db(db_path)
    monkeypatch.setattr(index_service, 'DEFAULT_DB_PATH', str(db_path))

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO index_jobs(job_type, payload_json) VALUES (?, ?)',
            ('mystery_job', '{}'),
        )
        conn.commit()

    sleep_calls = {'count': 0}

    def fake_sleep(_seconds):
        sleep_calls['count'] += 1
        if sleep_calls['count'] >= 3:
            raise _StopWorkerLoop()

    monkeypatch.setattr(index_service.time, 'sleep', fake_sleep)
    ctx.index_state.update({'state': 'empty', 'scope': 'cards', 'progress': 0, 'message': '', 'pending_jobs': 0})

    with pytest.raises(_StopWorkerLoop):
        index_service._worker_loop()

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            'SELECT status, error_msg FROM index_jobs WHERE job_type = ?',
            ('mystery_job',),
        ).fetchone()

    assert row[0] == 'failed'
    assert 'unsupported index job type' in row[1]
