import json
import logging
import os
import sqlite3

from core.config import CARDS_FOLDER, DEFAULT_DB_PATH, load_config
from core.data.index_runtime_store import get_active_generation
from core.data.ui_store import load_ui_data
from core.utils.image import extract_card_info
from core.utils.source_revision import build_file_source_revision


logger = logging.getLogger(__name__)


def _normalize_category_path(value: str) -> str:
    path = str(value or '').replace('\\', '/').strip().strip('/')
    if not path:
        return ''
    return '/'.join(part.strip() for part in path.split('/') if part.strip())


def _iter_category_ancestors(category: str):
    current = _normalize_category_path(category)
    while current:
        yield current
        if '/' not in current:
            break
        current = current.rsplit('/', 1)[0]


def _worldinfo_note_summary(ui_data: dict, source_type: str, *, file_path: str = '', card_id: str = '') -> str:
    if not isinstance(ui_data, dict):
        return ''
    notes = ui_data.get('_worldinfo_notes_v1') or {}
    if source_type == 'embedded':
        key = f'embedded::{card_id}'
    else:
        key = f'{source_type}::{str(file_path).replace("\\", "/")}'
    note = notes.get(key) or {}
    return str(note.get('summary') or '') if isinstance(note, dict) else ''


def _embedded_summary(ui_data: dict, card_id: str) -> str:
    if not isinstance(ui_data, dict):
        return ''
    card_meta = ui_data.get(card_id) or {}
    if isinstance(card_meta, dict):
        summary = str(card_meta.get('summary') or '')
        if summary.strip():
            return summary
    return _worldinfo_note_summary(ui_data, 'embedded', card_id=card_id)


def _insert_worldinfo_search(conn, generation: int, entity_id: str, *parts):
    content = ' '.join(str(part or '').strip() for part in parts if str(part or '').strip())
    conn.execute(
        'INSERT INTO index_search_fast_v2(generation, entity_id, content) VALUES (?, ?, ?)',
        (generation, entity_id, content),
    )
    conn.execute(
        'INSERT INTO index_search_full_v2(generation, entity_id, content) VALUES (?, ?, ?)',
        (generation, entity_id, content),
    )


def _rebuild_worldinfo_category_stats_v2(conn, generation: int, global_dir: str):
    conn.execute(
        'DELETE FROM index_category_stats_v2 WHERE generation = ? AND scope = ?',
        (generation, 'worldinfo'),
    )

    direct_counts = {}
    subtree_counts = {}

    rows = conn.execute(
        "SELECT entity_type, display_category FROM index_entities_v2 WHERE generation = ? AND entity_type LIKE 'world_%'",
        (generation,),
    ).fetchall()
    for row in rows:
        entity_type = str(row['entity_type'] or '')
        category = _normalize_category_path(row['display_category'])
        if not category:
            continue

        direct_counts[(entity_type, category)] = direct_counts.get((entity_type, category), 0) + 1
        direct_counts[('world_all', category)] = direct_counts.get(('world_all', category), 0) + 1

        for path in _iter_category_ancestors(category):
            subtree_counts[(entity_type, path)] = subtree_counts.get((entity_type, path), 0) + 1
            subtree_counts[('world_all', path)] = subtree_counts.get(('world_all', path), 0) + 1

    physical_paths = set()
    if global_dir and os.path.isdir(global_dir):
        for root, _dirs, _files in os.walk(global_dir):
            rel_root = os.path.relpath(root, global_dir).replace('\\', '/')
            current_category = '' if rel_root == '.' else _normalize_category_path(rel_root)
            if not current_category:
                continue
            for path in _iter_category_ancestors(current_category):
                physical_paths.add(path)

    stat_keys = set(direct_counts) | set(subtree_counts)
    stat_keys.update(('world_global', path) for path in physical_paths)
    stat_keys.update(('world_all', path) for path in physical_paths)

    for entity_type, category in sorted(stat_keys):
        conn.execute(
            'INSERT OR REPLACE INTO index_category_stats_v2(generation, scope, entity_type, category_path, direct_count, subtree_count) VALUES (?, ?, ?, ?, ?, ?)',
            (
                generation,
                'worldinfo',
                entity_type,
                category,
                int(direct_counts.get((entity_type, category), 0)),
                int(subtree_counts.get((entity_type, category), 0)),
            ),
        )


def _delete_worldinfo_entity_rows(conn, generation: int, entity_id: str):
    conn.execute(
        'DELETE FROM index_entities_v2 WHERE generation = ? AND entity_id = ?',
        (generation, entity_id),
    )
    conn.execute(
        'DELETE FROM index_entity_tags_v2 WHERE generation = ? AND entity_id = ?',
        (generation, entity_id),
    )
    conn.execute(
        'DELETE FROM index_search_fast_v2 WHERE generation = ? AND entity_id = ?',
        (generation, entity_id),
    )
    conn.execute(
        'DELETE FROM index_search_full_v2 WHERE generation = ? AND entity_id = ?',
        (generation, entity_id),
    )


def apply_worldinfo_path_increment(conn, source_path: str) -> bool:
    generation = get_active_generation(conn, 'worldinfo')
    if generation <= 0:
        raise RuntimeError('worldinfo active generation missing')

    cfg = load_config()
    ui_data = load_ui_data()
    normalized_path = os.path.normpath(str(source_path or ''))
    normalized_global_dir = os.path.normpath(str(cfg.get('world_info_dir') or ''))
    if not normalized_path or not normalized_global_dir:
        raise RuntimeError('worldinfo global directory unavailable')

    try:
        rel_path = os.path.relpath(normalized_path, normalized_global_dir).replace('\\', '/')
    except ValueError as exc:
        raise RuntimeError(f'worldinfo path outside global directory: {source_path}') from exc

    if rel_path.startswith('..'):
        raise RuntimeError(f'worldinfo path outside global directory: {source_path}')

    entity_id = f'world::global::{rel_path}'
    _delete_worldinfo_entity_rows(conn, generation, entity_id)

    if os.path.isfile(normalized_path):
        with open(normalized_path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        filename = os.path.basename(normalized_path)
        display_category = rel_path.rsplit('/', 1)[0] if '/' in rel_path else ''
        name = (data.get('name') or '').strip() or filename
        summary = _worldinfo_note_summary(ui_data, 'global', file_path=normalized_path)
        mtime = float(os.path.getmtime(normalized_path))
        conn.execute(
            '''
            INSERT OR REPLACE INTO index_entities_v2(
                generation, entity_id, entity_type, source_path, owner_entity_id, name, filename,
                display_category, physical_category, category_mode, favorite, summary_preview,
                updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                generation,
                entity_id,
                'world_global',
                normalized_path,
                '',
                name,
                filename,
                display_category,
                display_category,
                'physical',
                0,
                summary,
                mtime,
                0,
                0,
                name.lower(),
                mtime,
                '',
                build_file_source_revision(normalized_path),
            ),
        )
        _insert_worldinfo_search(conn, generation, entity_id, name, filename, display_category, summary)

    _rebuild_worldinfo_category_stats_v2(conn, generation, normalized_global_dir)
    conn.commit()
    return True


def apply_worldinfo_embedded_increment(conn, card_id: str, source_path: str = '') -> bool:
    generation = get_active_generation(conn, 'worldinfo')
    if generation <= 0:
        raise RuntimeError('worldinfo active generation missing')

    row = conn.execute(
        'SELECT id, char_name, category, character_book_name, last_modified, has_character_book FROM card_metadata WHERE id = ?',
        (card_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f'embedded owner card missing: {card_id}')

    card_path = str(source_path or os.path.join(CARDS_FOLDER, card_id.replace('/', os.sep)))
    entity_id = f'world::embedded::{card_id}'
    _delete_worldinfo_entity_rows(conn, generation, entity_id)

    if int(row['has_character_book'] or 0):
        info = extract_card_info(card_path)
        data = info.get('data', {}) if isinstance(info, dict) and 'data' in info else info
        book = data.get('character_book') if isinstance(data, dict) else None
        if isinstance(book, dict):
            ui_data = load_ui_data()
            name = str(book.get('name') or row['character_book_name'] or f"{row['char_name']}'s WI").strip()
            category = str(row['category'] or '')
            summary = _embedded_summary(ui_data, card_id)
            conn.execute(
                '''
                INSERT OR REPLACE INTO index_entities_v2(
                    generation, entity_id, entity_type, source_path, owner_entity_id, name, filename,
                    display_category, physical_category, category_mode, favorite, summary_preview,
                    updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    generation,
                    entity_id,
                    'world_embedded',
                    card_path,
                    f'card::{card_id}',
                    name,
                    os.path.basename(card_path),
                    category,
                    '',
                    'inherited',
                    0,
                    summary,
                    float(row['last_modified'] or 0),
                    0,
                    0,
                    name.lower(),
                    float(row['last_modified'] or 0),
                    '',
                    build_file_source_revision(card_path),
                ),
            )
            _insert_worldinfo_search(conn, generation, entity_id, name, os.path.basename(card_path), category, summary, str(row['char_name'] or ''))

    cfg = load_config()
    global_dir = str(cfg.get('world_info_dir') or '')
    _rebuild_worldinfo_category_stats_v2(conn, generation, global_dir)
    conn.commit()
    return True


def apply_worldinfo_owner_increment(conn, card_id: str, source_path: str = '') -> bool:
    generation = get_active_generation(conn, 'worldinfo')
    if generation <= 0:
        raise RuntimeError('worldinfo active generation missing')

    row = conn.execute(
        'SELECT id, char_name, category, last_modified, has_character_book, character_book_name FROM card_metadata WHERE id = ?',
        (card_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f'worldinfo owner card missing: {card_id}')

    apply_worldinfo_embedded_increment(conn, card_id, source_path)

    cfg = load_config()
    ui_data = load_ui_data()
    resources_dir = str(cfg.get('resources_dir') or '')
    owner_entity_id = f'card::{card_id}'

    existing_rows = conn.execute(
        'SELECT entity_id FROM index_entities_v2 WHERE generation = ? AND entity_type = ? AND owner_entity_id = ?',
        (generation, 'world_resource', owner_entity_id),
    ).fetchall()
    for existing_row in existing_rows:
        _delete_worldinfo_entity_rows(conn, generation, str(existing_row['entity_id'] or ''))

    resource_folder = str((ui_data.get(card_id) or {}).get('resource_folder', '')).strip()
    resource_item_categories = ((ui_data.get('_resource_item_categories_v1') or {}).get('worldinfo') or {})
    if resource_folder:
        lore_dir = os.path.join(resources_dir, resource_folder, 'lorebooks')
        if os.path.isdir(lore_dir):
            for filename in os.listdir(lore_dir):
                if not filename.lower().endswith('.json'):
                    continue
                full_path = os.path.join(lore_dir, filename)
                try:
                    with open(full_path, 'r', encoding='utf-8') as handle:
                        data = json.load(handle)
                except (OSError, json.JSONDecodeError):
                    logger.warning('Skipping invalid resource worldinfo file during owner increment: %s', full_path, exc_info=True)
                    continue

                path_key = str(full_path).replace('\\', '/').lower()
                override = (resource_item_categories.get(path_key) or {}).get('category', '')
                display_category = override or str(row['category'] or '')
                mode = 'override' if override else 'inherited'
                name = (data.get('name') or '').strip() or filename
                summary = _worldinfo_note_summary(ui_data, 'resource', file_path=full_path)
                mtime = float(os.path.getmtime(full_path))
                entity_id = f'world::resource::{card_id}::{filename}'
                conn.execute(
                    '''
                    INSERT OR REPLACE INTO index_entities_v2(
                        generation, entity_id, entity_type, source_path, owner_entity_id, name, filename,
                        display_category, physical_category, category_mode, favorite, summary_preview,
                        updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        generation,
                        entity_id,
                        'world_resource',
                        full_path,
                        owner_entity_id,
                        name,
                        filename,
                        display_category,
                        '',
                        mode,
                        0,
                        summary,
                        mtime,
                        0,
                        0,
                        name.lower(),
                        mtime,
                        '',
                        build_file_source_revision(full_path),
                    ),
                )
                _insert_worldinfo_search(
                    conn,
                    generation,
                    entity_id,
                    name,
                    filename,
                    display_category,
                    summary,
                    str(row['char_name'] or ''),
                )

    global_dir = str(cfg.get('world_info_dir') or '')
    _rebuild_worldinfo_category_stats_v2(conn, generation, global_dir)
    conn.commit()
    return True


def connect_index_db(db_path=None):
    conn = sqlite3.connect(db_path or DEFAULT_DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    return conn


def build_cards_generation(conn, generation: int):
    ui_data = load_ui_data()
    rows = conn.execute(
        'SELECT id, char_name, tags, category, last_modified, token_count, is_favorite FROM card_metadata'
    ).fetchall()

    for row in rows:
        entity_id = f"card::{row['id']}"
        tags = json.loads(row['tags'] or '[]') if row['tags'] else []
        summary = str((ui_data.get(row['id']) or {}).get('summary', ''))
        source_path = os.path.join(CARDS_FOLDER, row['id'].replace('/', os.sep))
        conn.execute(
            '''
            INSERT OR REPLACE INTO index_entities_v2(
                generation, entity_id, entity_type, source_path, owner_entity_id, name, filename,
                display_category, physical_category, category_mode, favorite, summary_preview,
                updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                generation,
                entity_id,
                'card',
                source_path,
                '',
                row['char_name'] or '',
                str(row['id']).split('/')[-1],
                row['category'] or '',
                row['category'] or '',
                'physical',
                int(row['is_favorite'] or 0),
                summary,
                float(row['last_modified'] or 0),
                0,
                int(row['token_count'] or 0),
                str(row['char_name'] or '').lower(),
                float(row['last_modified'] or 0),
                '',
                build_file_source_revision(source_path),
            ),
        )

        for tag in tags:
            normalized_tag = str(tag).strip()
            if not normalized_tag:
                continue
            conn.execute(
                'INSERT OR REPLACE INTO index_entity_tags_v2(generation, entity_id, tag) VALUES (?, ?, ?)',
                (generation, entity_id, normalized_tag),
            )

        content = ' '.join([
            str(row['char_name'] or ''),
            str(row['id']).split('/')[-1],
            str(row['category'] or ''),
            summary,
            ' '.join(str(tag) for tag in tags),
        ]).strip()
        conn.execute(
            'INSERT INTO index_search_fast_v2(generation, entity_id, content) VALUES (?, ?, ?)',
            (generation, entity_id, content),
        )
        conn.execute(
            'INSERT INTO index_search_full_v2(generation, entity_id, content) VALUES (?, ?, ?)',
            (generation, entity_id, content),
        )

    conn.commit()
    return len(rows)


def build_worldinfo_generation(conn, generation: int, inspected_books=None):
    cfg = load_config()
    ui_data = load_ui_data()
    global_dir = str(cfg.get('world_info_dir') or '')
    resources_dir = str(cfg.get('resources_dir') or '')
    rows = conn.execute(
        '''
        SELECT id, char_name, category, character_book_name, last_modified, has_character_book
        FROM card_metadata
        WHERE has_character_book = 1
        '''
    ).fetchall()
    inspected_books = inspected_books or {}

    items_written = 0

    if global_dir and os.path.isdir(global_dir):
        for root, _dirs, files in os.walk(global_dir):
            for filename in files:
                if not filename.lower().endswith('.json'):
                    continue
                full_path = os.path.join(root, filename)
                try:
                    with open(full_path, 'r', encoding='utf-8') as handle:
                        data = json.load(handle)
                except (OSError, json.JSONDecodeError):
                    logger.warning('Skipping invalid worldinfo file during v2 rebuild: %s', full_path, exc_info=True)
                    continue

                rel_path = os.path.relpath(full_path, global_dir).replace('\\', '/')
                display_category = rel_path.rsplit('/', 1)[0] if '/' in rel_path else ''
                name = (data.get('name') or '').strip() or filename
                entity_id = f'world::global::{rel_path}'
                summary = _worldinfo_note_summary(ui_data, 'global', file_path=full_path)
                mtime = float(os.path.getmtime(full_path))
                conn.execute(
                    '''
                    INSERT OR REPLACE INTO index_entities_v2(
                        generation, entity_id, entity_type, source_path, owner_entity_id, name, filename,
                        display_category, physical_category, category_mode, favorite, summary_preview,
                        updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        generation,
                        entity_id,
                        'world_global',
                        full_path,
                        '',
                        name,
                        filename,
                        display_category,
                        display_category,
                        'physical',
                        0,
                        summary,
                        mtime,
                        0,
                        0,
                        name.lower(),
                        mtime,
                        '',
                        build_file_source_revision(full_path),
                    ),
                )
                _insert_worldinfo_search(conn, generation, entity_id, name, filename, display_category, summary)
                items_written += 1

    resource_item_categories = ((ui_data.get('_resource_item_categories_v1') or {}).get('worldinfo') or {})
    for row in rows:
        card_id = str(row['id'])
        card_path = os.path.join(CARDS_FOLDER, card_id.replace('/', os.sep))
        owner_entity_id = f'card::{card_id}'
        resource_folder = str((ui_data.get(card_id) or {}).get('resource_folder', '')).strip()
        if resource_folder:
            lore_dir = os.path.join(resources_dir, resource_folder, 'lorebooks')
            if os.path.isdir(lore_dir):
                for filename in os.listdir(lore_dir):
                    if not filename.lower().endswith('.json'):
                        continue
                    full_path = os.path.join(lore_dir, filename)
                    try:
                        with open(full_path, 'r', encoding='utf-8') as handle:
                            data = json.load(handle)
                    except (OSError, json.JSONDecodeError):
                        logger.warning('Skipping invalid resource worldinfo file during v2 rebuild: %s', full_path, exc_info=True)
                        continue

                    path_key = str(full_path).replace('\\', '/').lower()
                    override = (resource_item_categories.get(path_key) or {}).get('category', '')
                    display_category = override or str(row['category'] or '')
                    mode = 'override' if override else 'inherited'
                    name = (data.get('name') or '').strip() or filename
                    summary = _worldinfo_note_summary(ui_data, 'resource', file_path=full_path)
                    mtime = float(os.path.getmtime(full_path))
                    entity_id = f'world::resource::{card_id}::{filename}'
                    conn.execute(
                        '''
                        INSERT OR REPLACE INTO index_entities_v2(
                            generation, entity_id, entity_type, source_path, owner_entity_id, name, filename,
                            display_category, physical_category, category_mode, favorite, summary_preview,
                            updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            generation,
                            entity_id,
                            'world_resource',
                            full_path,
                            owner_entity_id,
                            name,
                            filename,
                            display_category,
                            '',
                            mode,
                            0,
                            summary,
                            mtime,
                            0,
                            0,
                            name.lower(),
                            mtime,
                            '',
                            build_file_source_revision(full_path),
                        ),
                    )
                    _insert_worldinfo_search(
                        conn,
                        generation,
                        entity_id,
                        name,
                        filename,
                        display_category,
                        summary,
                        str(row['char_name'] or ''),
                    )
                    items_written += 1

        book = inspected_books.get(card_id)
        if book is None:
            info = extract_card_info(card_path)
            if not info:
                continue

            data = info.get('data', {}) if isinstance(info, dict) and 'data' in info else info
            book = data.get('character_book') if isinstance(data, dict) else None
        if not isinstance(book, dict):
            continue

        name = str(book.get('name') or row['character_book_name'] or f"{row['char_name']}'s WI").strip()
        entity_id = f'world::embedded::{card_id}'
        category = str(row['category'] or '')
        summary = _embedded_summary(ui_data, card_id)

        conn.execute(
            '''
            INSERT OR REPLACE INTO index_entities_v2(
                generation, entity_id, entity_type, source_path, owner_entity_id, name, filename,
                display_category, physical_category, category_mode, favorite, summary_preview,
                updated_at, import_time, token_count, sort_name, sort_mtime, thumb_url, source_revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                generation,
                entity_id,
                'world_embedded',
                card_path,
                owner_entity_id,
                name,
                os.path.basename(card_path),
                category,
                '',
                'inherited',
                0,
                summary,
                float(row['last_modified'] or 0),
                0,
                0,
                name.lower(),
                float(row['last_modified'] or 0),
                '',
                build_file_source_revision(card_path),
            ),
        )
        _insert_worldinfo_search(conn, generation, entity_id, name, os.path.basename(card_path), category, summary, str(row['char_name'] or ''))
        items_written += 1

    _rebuild_worldinfo_category_stats_v2(conn, generation, global_dir)
    conn.commit()
    return items_written
