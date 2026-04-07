import json
import sqlite3
import sys
import threading
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _StubCache:
    def __init__(self):
        self.cards = []
        self.visible_folders = []
        self.category_counts = {}
        self.global_tags = set()
        self.bundle_map = {}
        self.id_map = {}
        self.initialized = True
        self.lock = threading.Lock()

    def reload_from_db(self):
        return None


class _StubContext:
    def __init__(self):
        self.init_status = {
            'status': 'initializing',
            'message': '正在初始化...',
            'progress': 0,
            'total': 0,
        }
        self.cache = _StubCache()
        self.index_lock = threading.Lock()
        self.index_job_lock = threading.Lock()
        self.index_state = {
            'state': 'empty',
            'scope': 'cards',
            'progress': 0,
            'message': '',
            'pending_jobs': 0,
        }
        self.index_worker_started = False
        self.fs_ignore_until = 0
        self.wi_list_cache = {}
        self.wi_list_cache_lock = threading.Lock()

    def set_status(self, status=None, message=None, progress=None, total=None):
        if status is not None:
            self.init_status['status'] = status
        if message is not None:
            self.init_status['message'] = message
        if progress is not None:
            self.init_status['progress'] = progress
        if total is not None:
            self.init_status['total'] = total

    def update_fs_ignore(self, _seconds):
        self.fs_ignore_until = 0

    def should_ignore_fs_event(self):
        return False


sys.modules.setdefault('core.context', types.SimpleNamespace(ctx=_StubContext()))

from core import config as config_module
from core.data import db_session


def test_init_database_creates_index_tables(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    cards_dir = tmp_path / 'cards'
    cards_dir.mkdir()

    monkeypatch.setattr(db_session, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(db_session, 'CARDS_FOLDER', str(cards_dir))
    monkeypatch.setattr(db_session, '_migrate_existing_data', lambda conn: None)

    db_session.init_database()

    with sqlite3.connect(db_path) as conn:
        names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

    assert 'index_meta' in names
    assert 'index_entities' in names
    assert 'index_entity_tags' in names
    assert 'index_search_fast' in names
    assert 'index_search_full' in names
    assert 'index_category_stats' in names
    assert 'index_facet_stats' in names
    assert 'index_jobs' in names


def test_init_database_seeds_index_meta_defaults(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    cards_dir = tmp_path / 'cards'
    cards_dir.mkdir()

    monkeypatch.setattr(db_session, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(db_session, 'CARDS_FOLDER', str(cards_dir))
    monkeypatch.setattr(db_session, '_migrate_existing_data', lambda conn: None)

    db_session.init_database()

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            'SELECT value FROM index_meta WHERE key = ?',
            ('build_state',),
        ).fetchone()

    payload = json.loads(row[0])
    assert payload['state'] == 'empty'
    assert payload['scope'] == 'cards'


def test_default_config_exposes_index_flags():
    cfg = config_module.build_default_config()

    assert cfg['cards_list_use_index'] is False
    assert cfg['fast_search_use_index'] is False
    assert cfg['worldinfo_list_use_index'] is False
    assert cfg['index_auto_bootstrap'] is True


def test_stub_context_supports_index_and_card_api_imports():
    from core.context import ctx

    assert hasattr(ctx, 'cache')
    assert hasattr(ctx, 'index_state')
    assert hasattr(ctx, 'index_lock')
    assert hasattr(ctx, 'index_job_lock')
    assert hasattr(ctx, 'wi_list_cache')
    assert hasattr(ctx, 'wi_list_cache_lock')
    assert hasattr(ctx.cache, 'bundle_map')
    assert hasattr(ctx.cache, 'id_map')
