import sqlite3
import sys
import threading
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.api.v1 import world_info as world_info_api
from core.data.index_store import ensure_index_schema


class _FakeCache:
    def __init__(self, cards):
        self.cards = list(cards)
        self.visible_folders = []
        self.category_counts = {}
        self.global_tags = set()
        self.lock = threading.Lock()
        self.initialized = True

    def reload_from_db(self):
        raise AssertionError('reload_from_db should not run in indexed worldinfo list tests')


def _make_card(card_id, category, *, char_name='Lucy'):
    return {
        'id': card_id,
        'category': category,
        'char_name': char_name,
        'filename': card_id.split('/')[-1],
        'tags': [],
        'is_favorite': False,
        'ui_summary': '',
        'last_modified': 100.0,
        'import_time': 100.0,
        'token_count': 0,
        'has_character_book': False,
    }


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(world_info_api.bp)
    return app


def _seed_world_index(db_path):
    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO index_entities(entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('world::global::科幻/dragon.json', 'world_global', 'D:/lorebooks/科幻/dragon.json', '', 'Dragon Lore', 'dragon.json', '科幻', '科幻', 'physical', 0, 'lore', 300.0, 0.0, 0, 'dragon lore', 300.0, '', '300:1'),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_entities(entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('world::embedded::cards/lucy.png', 'world_embedded', 'D:/cards/lucy.png', 'card::cards/lucy.png', 'Embedded Book', 'lucy.png', '科幻', '', 'inherited', 0, 'embedded', 200.0, 0.0, 0, 'embedded book', 200.0, '', '200:1'),
        )
        conn.execute("INSERT OR REPLACE INTO index_search_fast(entity_id, content) VALUES (?, ?)", ('world::global::科幻/dragon.json', 'Dragon Lore 科幻 lore'))
        conn.execute("INSERT OR REPLACE INTO index_search_fast(entity_id, content) VALUES (?, ?)", ('world::embedded::cards/lucy.png', 'Embedded Book Lucy 科幻 embedded'))
        conn.commit()


def test_indexed_worldinfo_list_filters_type_category_and_search(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    monkeypatch.setattr(world_info_api, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {'worldinfo_list_use_index': True})
    _seed_world_index(db_path)

    client = _make_app().test_client()
    res = client.get('/api/world_info/list?type=global&category=科幻&search=dragon&page=1&page_size=20')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True
    assert [item['id'] for item in payload['items']] == ['global::科幻/dragon.json']
    assert [item['name'] for item in payload['items']] == ['Dragon Lore']


def test_indexed_worldinfo_list_folder_metadata_uses_full_source_set(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    lorebooks_dir = tmp_path / 'lorebooks'
    (lorebooks_dir / '科幻' / '空目录').mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(world_info_api, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {
        'worldinfo_list_use_index': True,
        'world_info_dir': str(lorebooks_dir),
        'resources_dir': str(tmp_path / 'resources'),
    })
    monkeypatch.setattr(world_info_api, 'load_ui_data', lambda: {})
    monkeypatch.setattr(world_info_api.ctx, 'cache', _FakeCache([]))

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO index_entities(entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('world::global::科幻/dragon.json', 'world_global', str(lorebooks_dir / '科幻' / 'dragon.json'), '', 'Dragon Lore', 'dragon.json', '科幻', '科幻', 'physical', 0, '', 300.0, 0.0, 0, 'dragon lore', 300.0, '', '300:1'),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_entities(entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('world::global::奇幻/forest.json', 'world_global', str(lorebooks_dir / '奇幻' / 'forest.json'), '', 'Forest Lore', 'forest.json', '奇幻', '奇幻', 'physical', 0, '', 200.0, 0.0, 0, 'forest lore', 200.0, '', '200:1'),
        )
        conn.commit()

    client = _make_app().test_client()
    res = client.get('/api/world_info/list?type=global&page=1&page_size=1')

    assert res.status_code == 200
    payload = res.get_json()
    assert [item['name'] for item in payload['items']] == ['Dragon Lore']
    assert '科幻' in payload['all_folders']
    assert '奇幻' in payload['all_folders']
    assert '科幻/空目录' in payload['all_folders']
    assert payload['category_counts']['科幻'] == 1
    assert payload['category_counts']['奇幻'] == 1
    assert payload['folder_capabilities']['科幻']['has_physical_folder'] is True
    assert payload['folder_capabilities']['科幻/空目录']['can_delete_physical_folder'] is True
    assert payload['folder_capabilities'][''].get('can_create_child_folder') is True


def test_indexed_worldinfo_resource_preserves_legacy_owner_fields_and_search(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    resource_file = tmp_path / 'resources' / 'lucy' / 'lorebooks' / 'companion.json'
    resource_file.parent.mkdir(parents=True, exist_ok=True)
    resource_file.write_text('{}', encoding='utf-8')

    monkeypatch.setattr(world_info_api, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {
        'worldinfo_list_use_index': True,
        'world_info_dir': str(tmp_path / 'lorebooks'),
        'resources_dir': str(tmp_path / 'resources'),
    })
    monkeypatch.setattr(world_info_api, 'load_ui_data', lambda: {
        '_worldinfo_notes_v1': {
            f"resource::{str(resource_file).replace('\\', '/').lower()}": {'summary': 'resource note'}
        },
        'cards/lucy.png': {'resource_folder': 'lucy'},
    })
    monkeypatch.setattr(world_info_api.ctx, 'cache', _FakeCache([_make_card('cards/lucy.png', '科幻', char_name='Lucy')]))

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO index_entities(entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('world::resource::cards/lucy.png::companion.json', 'world_resource', str(resource_file), 'card::cards/lucy.png', 'Companion Lore', 'companion.json', '科幻', '', 'inherited', 0, 'indexed summary only', 300.0, 0.0, 0, 'companion lore', 300.0, '', '300:1'),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_search_fast(entity_id, content) VALUES (?, ?)",
            ('world::resource::cards/lucy.png::companion.json', 'Companion Lore lorebook'),
        )
        conn.commit()

    client = _make_app().test_client()

    base_res = client.get('/api/world_info/list?type=resource')
    assert base_res.status_code == 200
    base_payload = base_res.get_json()
    assert len(base_payload['items']) == 1
    item = base_payload['items'][0]
    assert item['card_id'] == 'cards/lucy.png'
    assert item['card_name'] == 'Lucy'
    assert item['owner_card_id'] == 'cards/lucy.png'
    assert item['owner_card_name'] == 'Lucy'
    assert item['owner_card_category'] == '科幻'
    assert item['ui_summary'] == 'resource note'
    assert item['file_name'] == 'companion.json'
    assert item['name_source'] == 'meta'

    summary_res = client.get('/api/world_info/list?type=resource&search=resource%20note')
    assert summary_res.status_code == 200
    assert [entry['name'] for entry in summary_res.get_json()['items']] == ['Companion Lore']

    card_res = client.get('/api/world_info/list?type=resource&search=lucy')
    assert card_res.status_code == 200
    assert [entry['name'] for entry in card_res.get_json()['items']] == ['Companion Lore']


def test_indexed_worldinfo_search_preserves_name_substring_matching(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    monkeypatch.setattr(world_info_api, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {'worldinfo_list_use_index': True})
    monkeypatch.setattr(world_info_api, 'load_ui_data', lambda: {})
    monkeypatch.setattr(world_info_api.ctx, 'cache', _FakeCache([]))

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO index_entities(entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('world::global::科幻/super-dragon.json', 'world_global', 'D:/lorebooks/科幻/super-dragon.json', '', 'SuperDragonLore', 'super-dragon.json', '科幻', '科幻', 'physical', 0, '', 300.0, 0.0, 0, 'superdragonlore', 300.0, '', '300:1'),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_search_fast(entity_id, content) VALUES (?, ?)",
            ('world::global::科幻/super-dragon.json', 'unrelated tokens only'),
        )
        conn.commit()

    client = _make_app().test_client()
    res = client.get('/api/world_info/list?type=global&search=dragon')

    assert res.status_code == 200
    payload = res.get_json()
    assert [item['name'] for item in payload['items']] == ['SuperDragonLore']


def test_indexed_worldinfo_fast_search_preserves_name_substring_matching(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    monkeypatch.setattr(world_info_api, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {'worldinfo_list_use_index': True})
    monkeypatch.setattr(world_info_api, 'load_ui_data', lambda: {})
    monkeypatch.setattr(world_info_api.ctx, 'cache', _FakeCache([]))

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO index_entities(entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('world::global::科幻/super-dragon.json', 'world_global', 'D:/lorebooks/科幻/super-dragon.json', '', 'SuperDragonLore', 'super-dragon.json', '科幻', '科幻', 'physical', 0, '', 300.0, 0.0, 0, 'superdragonlore', 300.0, '', '300:1'),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_search_fast(entity_id, content) VALUES (?, ?)",
            ('world::global::科幻/super-dragon.json', 'unrelated tokens only'),
        )
        conn.commit()

    client = _make_app().test_client()
    res = client.get('/api/world_info/list?type=global&search=dragon&search_mode=fast')

    assert res.status_code == 200
    payload = res.get_json()
    assert [item['name'] for item in payload['items']] == ['SuperDragonLore']


def test_indexed_worldinfo_fulltext_search_uses_match_semantics(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    monkeypatch.setattr(world_info_api, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {'worldinfo_list_use_index': True})
    monkeypatch.setattr(world_info_api, 'load_ui_data', lambda: {})
    monkeypatch.setattr(world_info_api.ctx, 'cache', _FakeCache([]))

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO index_entities(entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('world::global::科幻/dragon.json', 'world_global', 'D:/lorebooks/科幻/dragon.json', '', 'Dragon Lore', 'dragon.json', '科幻', '科幻', 'physical', 0, '', 300.0, 0.0, 0, 'dragon lore', 300.0, '', '300:1'),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_search_fast(entity_id, content) VALUES (?, ?)",
            ('world::global::科幻/dragon.json', 'dragon hero rare pilot entry'),
        )
        conn.commit()

    client = _make_app().test_client()
    fast_res = client.get('/api/world_info/list?type=global&search=dragon%20AND%20hero&search_mode=fast')
    assert fast_res.status_code == 200
    assert fast_res.get_json()['items'] == []

    res = client.get('/api/world_info/list?type=global&search=dragon%20AND%20hero&search_mode=fulltext')

    assert res.status_code == 200
    payload = res.get_json()
    assert [item['id'] for item in payload['items']] == ['global::科幻/dragon.json']


def test_indexed_worldinfo_name_source_stays_meta_when_explicit_name_equals_filename(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    monkeypatch.setattr(world_info_api, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {'worldinfo_list_use_index': True})
    monkeypatch.setattr(world_info_api, 'load_ui_data', lambda: {})
    monkeypatch.setattr(world_info_api.ctx, 'cache', _FakeCache([]))

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO index_entities(entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('world::global::科幻/dragon.json', 'world_global', 'D:/lorebooks/科幻/dragon.json', '', 'dragon.json', 'dragon.json', '科幻', '科幻', 'physical', 0, '', 300.0, 0.0, 0, 'dragon.json', 300.0, '', '300:1'),
        )
        conn.commit()

    client = _make_app().test_client()
    res = client.get('/api/world_info/list?type=global')

    assert res.status_code == 200
    payload = res.get_json()
    assert len(payload['items']) == 1
    assert payload['items'][0]['name_source'] == 'meta'


def test_indexed_worldinfo_name_source_detects_filename_fallback_from_source_json(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'
    lorebooks_dir = tmp_path / 'lorebooks'
    source_file = lorebooks_dir / '科幻' / 'dragon.json'
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text('{"entries": {}}', encoding='utf-8')

    monkeypatch.setattr(world_info_api, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {
        'worldinfo_list_use_index': True,
        'world_info_dir': str(lorebooks_dir),
        'resources_dir': str(tmp_path / 'resources'),
    })
    monkeypatch.setattr(world_info_api, 'load_ui_data', lambda: {})
    monkeypatch.setattr(world_info_api.ctx, 'cache', _FakeCache([]))

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO index_entities(entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('world::global::科幻/dragon.json', 'world_global', str(source_file), '', 'dragon.json', 'dragon.json', '科幻', '科幻', 'physical', 0, '', 300.0, 0.0, 0, 'dragon.json', 300.0, '', '300:1'),
        )
        conn.commit()

    client = _make_app().test_client()
    res = client.get('/api/world_info/list?type=global')

    assert res.status_code == 200
    payload = res.get_json()
    assert len(payload['items']) == 1
    assert payload['items'][0]['name_source'] == 'filename'


def test_indexed_worldinfo_list_delegates_query_and_folder_metadata_to_index_helper(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    monkeypatch.setattr(world_info_api, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {'worldinfo_list_use_index': True})
    monkeypatch.setattr(world_info_api, 'load_ui_data', lambda: {})
    monkeypatch.setattr(world_info_api.ctx, 'cache', _FakeCache([]))

    seen_filters = []

    def _fake_query(filters):
        seen_filters.append(dict(filters))
        assert filters['paginate'] is True
        assert filters['type'] == 'global'
        assert filters['category'] == '科幻'
        assert filters['search'] == 'dragon'
        assert filters['page'] == 2
        assert filters['page_size'] == 1
        return {
            'items': [{
                'id': 'world::global::科幻/dragon.json',
                'type': 'global',
                'source_type': 'global',
                'name': 'Dragon Lore',
                'filename': 'dragon.json',
                'path': 'D:/lorebooks/科幻/dragon.json',
                'mtime': 300.0,
                'display_category': '科幻',
                'physical_category': '科幻',
                'category_mode': 'physical',
                'owner_entity_id': '',
            }],
            'total': 3,
            'all_folders': ['奇幻', '科幻'],
            'category_counts': {'奇幻': 2, '科幻': 1},
            'folder_capabilities': {
                '': {'can_create_child_folder': True},
                '科幻': {'has_physical_folder': True},
            },
        }

    monkeypatch.setattr(world_info_api, 'query_worldinfo_index', _fake_query)
    monkeypatch.setattr(
        world_info_api,
        '_add_physical_folder_nodes',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('_add_physical_folder_nodes should not run for indexed worldinfo list')),
    )

    client = _make_app().test_client()
    res = client.get('/api/world_info/list?type=global&category=科幻&search=dragon&page=2&page_size=1')

    assert res.status_code == 200
    payload = res.get_json()
    assert [item['id'] for item in payload['items']] == ['global::科幻/dragon.json']
    assert payload['total'] == 3
    assert payload['page'] == 2
    assert payload['page_size'] == 1
    assert payload['all_folders'] == ['奇幻', '科幻']
    assert payload['category_counts'] == {'奇幻': 2, '科幻': 1}
    assert payload['folder_capabilities']['科幻']['has_physical_folder'] is True
    assert seen_filters == [{
        'type': 'global',
        'category': '科幻',
        'search': 'dragon',
        'search_mode': 'fast',
        'page': 2,
        'page_size': 1,
        'db_path': str(db_path),
        'paginate': True,
    }]


def test_indexed_worldinfo_route_uses_subtree_counts_for_nested_categories(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    monkeypatch.setattr(world_info_api, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {'worldinfo_list_use_index': True})
    monkeypatch.setattr(world_info_api, 'load_ui_data', lambda: {})
    monkeypatch.setattr(world_info_api.ctx, 'cache', _FakeCache([]))

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO index_entities(entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('world::global::科幻/赛博朋克/dragon.json', 'world_global', 'D:/lorebooks/科幻/赛博朋克/dragon.json', '', 'Dragon Lore', 'dragon.json', '科幻/赛博朋克', '科幻/赛博朋克', 'physical', 0, '', 300.0, 0.0, 0, 'dragon lore', 300.0, '', '300:1'),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_category_stats(scope, entity_type, category_path, direct_count, subtree_count) VALUES (?, ?, ?, ?, ?)",
            ('worldinfo', 'world_global', '科幻', 0, 1),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_category_stats(scope, entity_type, category_path, direct_count, subtree_count) VALUES (?, ?, ?, ?, ?)",
            ('worldinfo', 'world_global', '科幻/赛博朋克', 1, 1),
        )
        conn.commit()

    client = _make_app().test_client()
    res = client.get('/api/world_info/list?type=global')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['category_counts']['科幻'] == 1
    assert payload['category_counts']['科幻/赛博朋克'] == 1


def test_indexed_worldinfo_route_keeps_virtual_folder_capabilities_for_resource_items(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    monkeypatch.setattr(world_info_api, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {'worldinfo_list_use_index': True})
    monkeypatch.setattr(world_info_api, 'load_ui_data', lambda: {})
    monkeypatch.setattr(world_info_api.ctx, 'cache', _FakeCache([_make_card('cards/lucy.png', '科幻', char_name='Lucy')]))

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO index_entities(entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('world::resource::cards/lucy.png::companion.json', 'world_resource', 'D:/resources/lucy/lorebooks/companion.json', 'card::cards/lucy.png', 'Companion Lore', 'companion.json', '科幻/伙伴', '', 'inherited', 0, '', 300.0, 0.0, 0, 'companion lore', 300.0, '', '300:1'),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_category_stats(scope, entity_type, category_path, direct_count, subtree_count) VALUES (?, ?, ?, ?, ?)",
            ('worldinfo', 'world_resource', '科幻', 0, 1),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_category_stats(scope, entity_type, category_path, direct_count, subtree_count) VALUES (?, ?, ?, ?, ?)",
            ('worldinfo', 'world_resource', '科幻/伙伴', 1, 1),
        )
        conn.commit()

    client = _make_app().test_client()
    res = client.get('/api/world_info/list?type=resource')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['folder_capabilities']['科幻']['has_physical_folder'] is False
    assert payload['folder_capabilities']['科幻']['has_virtual_items'] is True
    assert payload['folder_capabilities']['科幻']['can_create_child_folder'] is False
    assert payload['folder_capabilities']['科幻']['can_rename_physical_folder'] is False


def test_indexed_worldinfo_type_all_keeps_virtual_folder_capabilities_for_virtual_only_categories(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    monkeypatch.setattr(world_info_api, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {'worldinfo_list_use_index': True})
    monkeypatch.setattr(world_info_api, 'load_ui_data', lambda: {})
    monkeypatch.setattr(world_info_api.ctx, 'cache', _FakeCache([_make_card('cards/lucy.png', '科幻', char_name='Lucy')]))

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO index_entities(entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('world::resource::cards/lucy.png::companion.json', 'world_resource', 'D:/resources/lucy/lorebooks/companion.json', 'card::cards/lucy.png', 'Companion Lore', 'companion.json', '科幻/伙伴', '', 'inherited', 0, '', 300.0, 0.0, 0, 'companion lore', 300.0, '', '300:1'),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_category_stats(scope, entity_type, category_path, direct_count, subtree_count) VALUES (?, ?, ?, ?, ?)",
            ('worldinfo', 'world_all', '科幻', 0, 1),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_category_stats(scope, entity_type, category_path, direct_count, subtree_count) VALUES (?, ?, ?, ?, ?)",
            ('worldinfo', 'world_all', '科幻/伙伴', 1, 1),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_category_stats(scope, entity_type, category_path, direct_count, subtree_count) VALUES (?, ?, ?, ?, ?)",
            ('worldinfo', 'world_resource', '科幻', 0, 1),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_category_stats(scope, entity_type, category_path, direct_count, subtree_count) VALUES (?, ?, ?, ?, ?)",
            ('worldinfo', 'world_resource', '科幻/伙伴', 1, 1),
        )
        conn.commit()

    client = _make_app().test_client()
    res = client.get('/api/world_info/list?type=all')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['folder_capabilities']['科幻']['has_physical_folder'] is False
    assert payload['folder_capabilities']['科幻']['has_virtual_items'] is True
    assert payload['folder_capabilities']['科幻']['can_create_child_folder'] is False
    assert payload['folder_capabilities']['科幻']['can_rename_physical_folder'] is False


def test_indexed_worldinfo_route_malformed_search_preserves_literal_name_matching(monkeypatch, tmp_path):
    db_path = tmp_path / 'cards_metadata.db'

    monkeypatch.setattr(world_info_api, 'DEFAULT_DB_PATH', str(db_path))
    monkeypatch.setattr(world_info_api, 'load_config', lambda: {'worldinfo_list_use_index': True})
    monkeypatch.setattr(world_info_api, 'load_ui_data', lambda: {})
    monkeypatch.setattr(world_info_api.ctx, 'cache', _FakeCache([]))

    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO index_entities(entity_id, entity_type, source_path, owner_entity_id, name, filename, display_category, physical_category, category_mode, favorite, summary_preview, updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('world::global::科幻/broken[query].json', 'world_global', 'D:/lorebooks/科幻/broken[query].json', '', 'broken[query] lore', 'broken[query].json', '科幻', '科幻', 'physical', 0, '', 300.0, 0.0, 0, 'broken[query] lore', 300.0, '', '300:1'),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_category_stats(scope, entity_type, category_path, direct_count, subtree_count) VALUES (?, ?, ?, ?, ?)",
            ('worldinfo', 'world_global', '科幻', 1, 1),
        )
        conn.commit()

    client = _make_app().test_client()
    res = client.get('/api/world_info/list?type=global&search=broken%5Bquery')

    assert res.status_code == 200
    payload = res.get_json()
    assert [item['name'] for item in payload['items']] == ['broken[query] lore']
