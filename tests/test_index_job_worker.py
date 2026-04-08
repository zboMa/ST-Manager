import sqlite3
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.context import ctx
from core.data.index_runtime_store import ensure_index_runtime_schema
from core.services import index_job_worker


def test_enqueue_index_job_sets_worker_event(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    with sqlite3.connect(db_path) as conn:
        ensure_index_runtime_schema(conn)

    monkeypatch.setattr(index_job_worker, 'DEFAULT_DB_PATH', str(db_path))
    ctx.index_wakeup.clear()

    index_job_worker.enqueue_index_job('upsert_card', entity_id='hero.png', source_path='hero.png')

    assert ctx.index_wakeup.is_set() is True


def test_worker_waits_on_event_before_querying_jobs(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    with sqlite3.connect(db_path) as conn:
        ensure_index_runtime_schema(conn)

    monkeypatch.setattr(index_job_worker, 'DEFAULT_DB_PATH', str(db_path))

    waits = []

    class _StopLoop(Exception):
        pass

    def fake_wait(timeout):
        waits.append(timeout)
        raise _StopLoop()

    monkeypatch.setattr(ctx.index_wakeup, 'wait', fake_wait)

    try:
        index_job_worker.worker_loop()
    except _StopLoop:
        pass

    assert waits == [30]


def test_enqueue_index_job_updates_visible_pending_jobs_immediately(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    with sqlite3.connect(db_path) as conn:
        ensure_index_runtime_schema(conn)

    monkeypatch.setattr(index_job_worker, 'DEFAULT_DB_PATH', str(db_path))
    ctx.index_state.update({'pending_jobs': 0})
    ctx.index_state['jobs']['pending_jobs'] = 0

    index_job_worker.enqueue_index_job('upsert_card', entity_id='hero.png', source_path='hero.png')

    assert ctx.index_state['jobs']['pending_jobs'] == 1
    assert ctx.index_state['pending_jobs'] == 1


def test_enqueue_index_job_skips_duplicate_pending_job(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    with sqlite3.connect(db_path) as conn:
        ensure_index_runtime_schema(conn)

    monkeypatch.setattr(index_job_worker, 'DEFAULT_DB_PATH', str(db_path))

    index_job_worker.enqueue_index_job('upsert_worldinfo_path', source_path='D:/data/lorebooks/book.json')
    index_job_worker.enqueue_index_job('upsert_worldinfo_path', source_path='D:/data/lorebooks/book.json')

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            'SELECT job_type, status, source_path FROM index_jobs ORDER BY id'
        ).fetchall()

    assert rows == [('upsert_worldinfo_path', 'pending', 'D:/data/lorebooks/book.json')]


def test_enqueue_index_job_hot_path_does_not_reensure_schema(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    with sqlite3.connect(db_path) as conn:
        ensure_index_runtime_schema(conn)

    monkeypatch.setattr(index_job_worker, 'DEFAULT_DB_PATH', str(db_path))

    def _boom(_conn):
        raise AssertionError('ensure_index_runtime_schema should not be called from enqueue hot path')

    monkeypatch.setattr(index_job_worker, 'ensure_index_runtime_schema', _boom)

    index_job_worker.enqueue_index_job('upsert_card', entity_id='hero.png', source_path='hero.png')

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            'SELECT job_type, entity_id, source_path, status FROM index_jobs ORDER BY id DESC LIMIT 1'
        ).fetchone()

    assert row == ('upsert_card', 'hero.png', 'hero.png', 'pending')


def test_worker_claims_pending_jobs_before_processing(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    with sqlite3.connect(db_path) as conn:
        ensure_index_runtime_schema(conn)
        conn.execute(
            'INSERT INTO index_jobs(job_type, payload_json) VALUES (?, ?)',
            ('rebuild_scope', '{"scope": "cards"}'),
        )
        conn.commit()

    monkeypatch.setattr(index_job_worker, 'DEFAULT_DB_PATH', str(db_path))

    class _StopLoop(Exception):
        pass

    wait_calls = {'count': 0}
    observed = {}

    def fake_wait(_timeout):
        wait_calls['count'] += 1
        if wait_calls['count'] >= 2:
            raise _StopLoop()
        return True

    def fake_rebuild_scope_generation(_scope='cards', reason='bootstrap'):
        with sqlite3.connect(db_path) as conn:
            observed['status'] = conn.execute('SELECT status FROM index_jobs WHERE id = 1').fetchone()[0]

    monkeypatch.setattr(ctx.index_wakeup, 'wait', fake_wait)
    monkeypatch.setattr(index_job_worker, 'rebuild_scope_generation', fake_rebuild_scope_generation)
    ctx.index_wakeup.set()

    with pytest.raises(_StopLoop):
        index_job_worker.worker_loop()

    assert observed['status'] == 'running'


def test_start_index_job_worker_starts_only_one_thread(monkeypatch):
    started = []

    class _FakeThread:
        def __init__(self, *, target=None, daemon=None):
            self.target = target
            self.daemon = daemon

        def start(self):
            started.append(self.target)

    monkeypatch.setattr(index_job_worker.threading, 'Thread', _FakeThread)
    ctx.index_worker_started = False

    index_job_worker.start_index_job_worker()
    index_job_worker.start_index_job_worker()

    assert started == [index_job_worker.worker_loop]


def test_claim_pending_jobs_returns_only_rows_claimed_by_current_invocation(monkeypatch, tmp_path):
    class _FakeResult:
        def __init__(self, *, rows=None, scalar=None):
            self._rows = rows or []
            self._scalar = scalar

        def fetchall(self):
            return self._rows

        def fetchone(self):
            return [self._scalar]

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params=()):
            normalized = ' '.join(str(sql).split()).lower()
            if normalized.startswith('select id from index_jobs where status = '):
                return _FakeResult(rows=[{'id': 1}])
            if normalized.startswith('update index_jobs set status = ?'):
                self._claim_token = params[1]
                return _FakeResult()
            if 'select id, job_type, entity_id, source_path, payload_json from index_jobs' in normalized:
                if len(params) >= 2 and params[1] == getattr(self, '_claim_token', None):
                    return _FakeResult(rows=[])
                return _FakeResult(rows=[{'id': 1, 'job_type': 'rebuild_scope', 'entity_id': '', 'source_path': '', 'payload_json': '{}'}])
            if normalized.startswith('select count(*) from index_jobs where status = '):
                return _FakeResult(scalar=0)
            raise AssertionError(f'unexpected sql: {sql}')

        def commit(self):
            return None

    monkeypatch.setattr(index_job_worker, '_connect', lambda: _FakeConn())

    claimed_rows, pending = index_job_worker._claim_pending_jobs(50)

    assert claimed_rows == []
    assert pending == 0
