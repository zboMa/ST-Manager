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


def test_worldinfo_detail_search_returns_matching_entry_indexes():
    client = _make_app().test_client()

    res = client.post('/api/world_info/detail_search', json={
        'query': 'dragon',
        'data': {
            'entries': [
                {'keys': ['hero'], 'content': 'alpha'},
                {'keys': ['dragon'], 'content': 'beta'},
            ]
        },
    })

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True
    assert payload['items'] == [{'index': 1}]


def test_worldinfo_detail_search_matches_comment_and_content_case_insensitively():
    client = _make_app().test_client()

    res = client.post('/api/world_info/detail_search', json={
        'query': 'dragon',
        'data': {
            'entries': [
                {'keys': ['hero'], 'content': 'Alpha DRAGON'},
                {'keys': ['villain'], 'comment': 'dragon note', 'content': 'beta'},
                {'keys': ['sidekick'], 'content': 'gamma'},
            ]
        },
    })

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True
    assert payload['items'] == [{'index': 0}, {'index': 1}]


def test_worldinfo_detail_search_returns_empty_items_for_blank_query():
    client = _make_app().test_client()

    res = client.post('/api/world_info/detail_search', json={
        'query': '   ',
        'data': {
            'entries': [
                {'keys': ['dragon'], 'content': 'beta'},
            ]
        },
    })

    assert res.status_code == 200
    payload = res.get_json()
    assert payload == {'success': True, 'items': []}


def test_worldinfo_detail_search_supports_normalized_dict_entries_payload():
    client = _make_app().test_client()

    res = client.post('/api/world_info/detail_search', json={
        'query': 'dragon',
        'data': {
            'entries': {
                '0': {'keys': ['hero'], 'content': 'alpha'},
                '1': {'keys': ['villain'], 'comment': 'dragon note', 'content': 'beta'},
            }
        },
    })

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True
    assert payload['items'] == [{'index': 1}]


def test_worldinfo_detail_search_matches_secondary_and_legacy_key_fields():
    client = _make_app().test_client()

    res = client.post('/api/world_info/detail_search', json={
        'query': 'dragon',
        'data': {
            'entries': [
                {'keys': ['hero'], 'secondary_keys': ['dragon'], 'content': 'alpha'},
                {'keys': ['villain'], 'keysecondary': ['dragon'], 'content': 'beta'},
                {'key': ['dragon'], 'content': 'gamma'},
                {'keys': ['sidekick'], 'content': 'delta'},
            ]
        },
    })

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True
    assert payload['items'] == [{'index': 0}, {'index': 1}, {'index': 2}]
