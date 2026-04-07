import json
import sys
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.api.v1 import world_info as world_info_api


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(world_info_api.bp)
    return app


def test_worldinfo_detail_returns_source_revision(monkeypatch, tmp_path):
    lore_dir = tmp_path / 'lorebooks'
    lore_dir.mkdir()
    book = lore_dir / 'main.json'
    book.write_text(json.dumps({'name': 'Main', 'entries': {}}, ensure_ascii=False), encoding='utf-8')

    monkeypatch.setattr(world_info_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {'world_info_dir': str(lore_dir), 'resources_dir': str(tmp_path / 'resources')})
    monkeypatch.setattr(world_info_api, 'load_ui_data', lambda: {})

    client = _make_app().test_client()
    res = client.post('/api/world_info/detail', json={'source_type': 'global', 'file_path': str(book)})

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True
    assert payload['source_revision']


def test_worldinfo_save_rejects_stale_source_revision(monkeypatch, tmp_path):
    lore_dir = tmp_path / 'lorebooks'
    lore_dir.mkdir()
    book = lore_dir / 'main.json'
    book.write_text(json.dumps({'name': 'Main', 'entries': {}}, ensure_ascii=False), encoding='utf-8')

    monkeypatch.setattr(world_info_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {'world_info_dir': str(lore_dir), 'resources_dir': str(tmp_path / 'resources')})

    client = _make_app().test_client()
    res = client.post('/api/world_info/save', json={
        'save_mode': 'overwrite',
        'file_path': str(book),
        'content': {'name': 'Main', 'entries': {}},
        'source_revision': '1:1',
    })

    assert res.status_code == 409
    payload = res.get_json()
    assert payload['success'] is False
    assert 'source_revision' in payload['msg']


def test_worldinfo_save_returns_updated_source_revision(monkeypatch, tmp_path):
    lore_dir = tmp_path / 'lorebooks'
    lore_dir.mkdir()
    book = lore_dir / 'main.json'
    book.write_text(json.dumps({'name': 'Main', 'entries': {}}, ensure_ascii=False), encoding='utf-8')

    monkeypatch.setattr(world_info_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {'world_info_dir': str(lore_dir), 'resources_dir': str(tmp_path / 'resources')})

    client = _make_app().test_client()
    detail_res = client.post('/api/world_info/detail', json={'source_type': 'global', 'file_path': str(book)})
    detail_payload = detail_res.get_json()

    save_res = client.post('/api/world_info/save', json={
        'save_mode': 'overwrite',
        'file_path': str(book),
        'content': {'name': 'Main Updated', 'entries': {}},
        'source_revision': detail_payload['source_revision'],
    })

    assert save_res.status_code == 200
    payload = save_res.get_json()
    assert payload['success'] is True
    assert payload['source_revision']
    assert payload['source_revision'] != detail_payload['source_revision']


def test_worldinfo_save_requires_source_revision_for_overwrite(monkeypatch, tmp_path):
    lore_dir = tmp_path / 'lorebooks'
    lore_dir.mkdir()
    book = lore_dir / 'main.json'
    book.write_text(json.dumps({'name': 'Main', 'entries': {}}, ensure_ascii=False), encoding='utf-8')

    monkeypatch.setattr(world_info_api, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {'world_info_dir': str(lore_dir), 'resources_dir': str(tmp_path / 'resources')})

    client = _make_app().test_client()
    save_res = client.post('/api/world_info/save', json={
        'save_mode': 'overwrite',
        'file_path': str(book),
        'content': {'name': 'Main Updated', 'entries': {}},
    })

    assert save_res.status_code == 409
    payload = save_res.get_json()
    assert payload['success'] is False
    assert 'source_revision' in payload['msg']
