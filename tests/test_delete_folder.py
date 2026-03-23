import sys
import json
import os
import sqlite3
from pathlib import Path

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.api.v1 import cards as cards_api
from core.data import db_session as db_session_module
from core.data import ui_store as ui_store_module
from core.context import ctx


def _make_test_app():
    app = Flask(__name__)
    app.register_blueprint(cards_api.bp)
    return app


def _init_db(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS card_metadata (
            id TEXT PRIMARY KEY,
            category TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def _insert_card_meta(db_path: Path, *, card_id: str, category: str):
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO card_metadata (id, category) VALUES (?, ?)",
        (card_id, category),
    )
    conn.commit()
    conn.close()


def _read_ui_data(ui_path: Path):
    if not ui_path.exists():
        return {}
    return json.loads(ui_path.read_text(encoding='utf-8'))


@pytest.fixture()
def folder_fixture(tmp_path):
    cards_dir = tmp_path / 'cards'
    trash_dir = tmp_path / 'trash'
    db_path = tmp_path / 'db.sqlite'
    ui_path = tmp_path / 'ui_data.json'

    cards_dir.mkdir(parents=True, exist_ok=True)
    trash_dir.mkdir(parents=True, exist_ok=True)

    _init_db(db_path)

    # 文件结构：
    # cards/testA/a.png
    # cards/testA/sub/b.png
    (cards_dir / 'testA' / 'sub').mkdir(parents=True, exist_ok=True)
    (cards_dir / 'testA' / 'a.png').write_bytes(b'png')
    (cards_dir / 'testA' / 'sub' / 'b.png').write_bytes(b'png')

    _insert_card_meta(db_path, card_id='testA/a.png', category='testA')
    _insert_card_meta(db_path, card_id='testA/sub/b.png', category='testA/sub')

    ui_path.write_text(
        json.dumps(
            {
                'testA/a.png': {'summary': 'a'},
                'testA/sub/b.png': {'summary': 'b'},
                'testA/sub': {'summary': 'bundle-sub'},
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    return {
        'cards_dir': cards_dir,
        'trash_dir': trash_dir,
        'db_path': db_path,
        'ui_path': ui_path,
    }


def test_delete_folder_dissolve_moves_children(monkeypatch, folder_fixture):
    cards_dir = folder_fixture['cards_dir']
    trash_dir = folder_fixture['trash_dir']
    db_path = folder_fixture['db_path']
    ui_path = folder_fixture['ui_path']

    monkeypatch.setattr(cards_api, 'CARDS_FOLDER', str(cards_dir))
    monkeypatch.setattr(cards_api, 'TRASH_FOLDER', str(trash_dir))
    monkeypatch.setattr(db_session_module, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(ui_store_module, 'UI_DATA_FILE', str(ui_path))

    monkeypatch.setattr(cards_api, 'schedule_reload', lambda *args, **kwargs: None)
    monkeypatch.setattr(cards_api, 'force_reload', lambda *args, **kwargs: None)
    monkeypatch.setattr(cards_api, 'suppress_fs_events', lambda *args, **kwargs: None)

    # 避免增量缓存对测试结果产生干扰
    ctx.cache.visible_folders = ['testA']

    client = _make_test_app().test_client()
    res = client.post('/api/delete_folder', json={'folder_path': 'testA'})
    payload = res.get_json()

    assert payload['success'] is True
    assert payload['moved_count'] == 2

    # filesystem: 内容移动到上一级目录，testA 被删除
    assert not (cards_dir / 'testA').exists()
    assert (cards_dir / 'a.png').exists()
    assert (cards_dir / 'sub').is_dir()
    assert (cards_dir / 'sub' / 'b.png').exists()

    # db: id / category 按移动规则更新
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM card_metadata")
    ids = {row[0] for row in cursor.fetchall()}
    conn.close()
    assert ids == {'a.png', 'sub/b.png'}

    # ui_data: key 按移动规则更新
    ui_after = _read_ui_data(ui_path)
    assert 'testA/a.png' not in ui_after
    assert 'a.png' in ui_after
    assert 'testA/sub' not in ui_after
    assert 'sub' in ui_after


def test_delete_folder_delete_children_recursive(monkeypatch, folder_fixture):
    cards_dir = folder_fixture['cards_dir']
    trash_dir = folder_fixture['trash_dir']
    db_path = folder_fixture['db_path']
    ui_path = folder_fixture['ui_path']

    monkeypatch.setattr(cards_api, 'CARDS_FOLDER', str(cards_dir))
    monkeypatch.setattr(cards_api, 'TRASH_FOLDER', str(trash_dir))
    monkeypatch.setattr(db_session_module, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(ui_store_module, 'UI_DATA_FILE', str(ui_path))

    monkeypatch.setattr(cards_api, 'schedule_reload', lambda *args, **kwargs: None)
    monkeypatch.setattr(cards_api, 'force_reload', lambda *args, **kwargs: None)
    monkeypatch.setattr(cards_api, 'suppress_fs_events', lambda *args, **kwargs: None)

    # 可见文件夹列表包含子目录时也应被清理
    ctx.cache.visible_folders = ['testA', 'testA/sub']

    client = _make_test_app().test_client()
    res = client.post('/api/delete_folder', json={'folder_path': 'testA', 'delete_children': True})
    payload = res.get_json()

    assert payload['success'] is True
    assert payload['deleted_children'] is True
    assert payload['deleted_count'] == 2

    # filesystem: testA 不在 cards_dir，且被移动到 trash
    assert not (cards_dir / 'testA').exists()
    trash_entries = list(trash_dir.iterdir())
    assert len(trash_entries) == 1
    assert trash_entries[0].name.startswith('testA_')

    # db: 目录下的所有卡片元数据被删除
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM card_metadata")
    rows = cursor.fetchall()
    conn.close()
    assert rows == []

    # ui_data: 目录下的所有 UI keys 被删除
    ui_after = _read_ui_data(ui_path)
    assert ui_after == {}

