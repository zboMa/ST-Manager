import os
import sqlite3

from core.config import DEFAULT_DB_PATH


def _connect(db_path=None):
    conn = sqlite3.connect(db_path or DEFAULT_DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _is_malformed_match_error(exc):
    message = str(exc or '').lower()
    malformed_markers = (
        'fts5: syntax error',
        'unterminated string',
        'malformed match expression',
    )
    return any(marker in message for marker in malformed_markers)


def _normalized_category(value: str) -> str:
    path = str(value or '').replace('\\', '/').strip().strip('/')
    if not path:
        return ''
    return '/'.join(part.strip() for part in path.split('/') if part.strip())


def _world_entity_type(requested_type: str) -> str:
    type_map = {
        'global': 'world_global',
        'resource': 'world_resource',
        'embedded': 'world_embedded',
    }
    return type_map.get(str(requested_type or '').strip().lower(), 'world_all')


def _build_folder_capabilities(all_folders, folder_semantics=None):
    semantics = folder_semantics or {}
    folder_capabilities = {
        '': {
            'has_physical_folder': True,
            'has_virtual_items': bool(semantics.get('', {}).get('has_virtual_items', False)),
            'can_create_child_folder': True,
            'can_rename_physical_folder': False,
            'can_delete_physical_folder': False,
        }
    }
    for path in all_folders:
        meta = semantics.get(path) or {}
        has_physical_folder = bool(meta.get('has_physical_folder', False))
        has_virtual_items = bool(meta.get('has_virtual_items', False))
        folder_capabilities[path] = {
            'has_physical_folder': has_physical_folder,
            'has_virtual_items': has_virtual_items,
            'can_create_child_folder': has_physical_folder,
            'can_rename_physical_folder': has_physical_folder,
            'can_delete_physical_folder': False,
        }
    return folder_capabilities


def _iter_category_ancestors(category: str):
    current = _normalized_category(category)
    while current:
        yield current
        if '/' not in current:
            break
        current = current.rsplit('/', 1)[0]


def _fallback_folder_metadata(conn, requested_entity_type: str):
    where = ["entity_type LIKE 'world_%'"]
    params = []
    if requested_entity_type != 'world_all':
        where.append('entity_type = ?')
        params.append(requested_entity_type)

    rows = conn.execute(
        f"SELECT entity_type, display_category, source_path FROM index_entities WHERE {' AND '.join(where)}",
        params,
    ).fetchall()

    category_counts = {}
    all_folders = set()
    global_roots = set()
    empty_physical_folders = set()
    folder_semantics = {'': {'has_physical_folder': True, 'has_virtual_items': False}}

    def _ensure_semantics(path):
        if path not in folder_semantics:
            folder_semantics[path] = {'has_physical_folder': False, 'has_virtual_items': False}
        return folder_semantics[path]

    for row in rows:
        category = _normalized_category(row['display_category'])
        entity_type = str(row['entity_type'] or '')
        if category:
            for path in _iter_category_ancestors(category):
                category_counts[path] = category_counts.get(path, 0) + 1
                meta = _ensure_semantics(path)
                if entity_type == 'world_global':
                    meta['has_physical_folder'] = True
                else:
                    meta['has_virtual_items'] = True
            for path in _iter_category_ancestors(category):
                all_folders.add(path)

        if entity_type == 'world_global':
            source_path = str(row['source_path'] or '').replace('\\', '/')
            if source_path and category and source_path.lower().endswith('/' + category.lower() + '/' + source_path.split('/')[-1].lower()):
                root_path = source_path[:-(len(category) + len(source_path.split('/')[-1]) + 2)]
                if root_path:
                    global_roots.add(root_path.rstrip('/'))

    for root in sorted(global_roots):
        if not root:
            continue
        try:
            for current_root, dirs, _files in os.walk(root):
                rel_root = os.path.relpath(current_root, root).replace('\\', '/')
                current_category = '' if rel_root == '.' else _normalized_category(rel_root)
                if not current_category:
                    continue
                for path in _iter_category_ancestors(current_category):
                    all_folders.add(path)
                    _ensure_semantics(path)['has_physical_folder'] = True
                if not dirs and not _files:
                    empty_physical_folders.add(current_category)
        except Exception:
            continue

    return sorted(all_folders), category_counts, empty_physical_folders, folder_semantics


def _category_stats_metadata(conn, requested_entity_type: str):
    stat_rows = conn.execute(
        'SELECT category_path, direct_count, subtree_count FROM index_category_stats WHERE scope = ? AND entity_type = ? ORDER BY category_path ASC',
        ('worldinfo', requested_entity_type),
    ).fetchall()
    if not stat_rows:
        return None

    all_folders = [str(row['category_path'] or '') for row in stat_rows if str(row['category_path'] or '')]
    category_counts = {
        str(row['category_path'] or ''): int(row['subtree_count'] or 0)
        for row in stat_rows
        if str(row['category_path'] or '')
    }
    folder_semantics = {'': {'has_physical_folder': True, 'has_virtual_items': False}}
    empty_physical_folders = set()

    def _stat_count(entity_type: str, path: str) -> int:
        row = conn.execute(
            'SELECT subtree_count FROM index_category_stats WHERE scope = ? AND entity_type = ? AND category_path = ?',
            ('worldinfo', entity_type, path),
        ).fetchone()
        return int((row or [0])[0] or 0)

    def _has_stat_row(entity_type: str, path: str) -> bool:
        row = conn.execute(
            'SELECT 1 FROM index_category_stats WHERE scope = ? AND entity_type = ? AND category_path = ? LIMIT 1',
            ('worldinfo', entity_type, path),
        ).fetchone()
        return row is not None

    def _has_physical_child_folder(path: str) -> bool:
        prefix = f'{path}/%'
        row = conn.execute(
            'SELECT 1 FROM index_category_stats WHERE scope = ? AND entity_type = ? AND category_path LIKE ? LIMIT 1',
            ('worldinfo', 'world_global', prefix),
        ).fetchone()
        return row is not None

    for row in stat_rows:
        path = str(row['category_path'] or '')
        if not path:
            continue
        has_count = int(row['subtree_count'] or 0) > 0
        if requested_entity_type == 'world_global':
            folder_semantics[path] = {'has_physical_folder': True, 'has_virtual_items': False}
            if not has_count and not _has_physical_child_folder(path):
                empty_physical_folders.add(path)
        elif requested_entity_type == 'world_all':
            has_physical_folder = _has_stat_row('world_global', path)
            physical_count = _stat_count('world_global', path)
            resource_count = _stat_count('world_resource', path)
            embedded_count = _stat_count('world_embedded', path)
            folder_semantics[path] = {
                'has_physical_folder': has_physical_folder,
                'has_virtual_items': bool(resource_count > 0 or embedded_count > 0),
            }
            if has_physical_folder and physical_count == 0 and not _has_physical_child_folder(path):
                empty_physical_folders.add(path)
        else:
            folder_semantics[path] = {'has_physical_folder': False, 'has_virtual_items': has_count}

    return all_folders, category_counts, empty_physical_folders, folder_semantics


def _build_query_parts(filters, *, literal_only=False):
    where = ["e.entity_type LIKE 'world_%'"]
    params = []
    search_mode = str(filters.get('search_mode') or 'fast').strip().lower()
    if search_mode not in ('fast', 'fulltext'):
        search_mode = 'fast'

    requested_type = str(filters.get('type') or 'all').strip().lower()
    requested_entity_type = _world_entity_type(requested_type)
    if requested_entity_type != 'world_all':
        where.append('e.entity_type = ?')
        params.append(requested_entity_type)

    category = _normalized_category(filters.get('category') or '')
    if category:
        where.append('(e.display_category = ? OR e.display_category LIKE ?)')
        params.extend([category, f'{category}/%'])

    search = str(filters.get('search') or '').strip()
    if search:
        search_terms = ['LOWER(e.name) LIKE ?']
        search_params = [f'%{search.lower()}%']

        if not literal_only and search_mode == 'fulltext':
            search_terms.insert(0, 'e.entity_id IN (SELECT entity_id FROM index_search_fast WHERE index_search_fast MATCH ?)')
            search_params.insert(0, search)
        elif not literal_only:
            search_terms.insert(0, 'e.entity_id IN (SELECT entity_id FROM index_search_fast WHERE content LIKE ? ESCAPE \'\\\')')
            escaped = search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            search_params.insert(0, f'%{escaped.lower()}%')

        extra_source_paths = [str(path) for path in (filters.get('source_paths') or []) if str(path).strip()]
        if extra_source_paths:
            placeholders = ', '.join('?' for _ in extra_source_paths)
            search_terms.append(f"LOWER(REPLACE(e.source_path, '\\', '/')) IN ({placeholders})")
            search_params.extend(str(path).replace('\\', '/').lower() for path in extra_source_paths)

        extra_owner_entity_ids = [str(value) for value in (filters.get('owner_entity_ids') or []) if str(value).strip()]
        if extra_owner_entity_ids:
            placeholders = ', '.join('?' for _ in extra_owner_entity_ids)
            search_terms.append(f'e.owner_entity_id IN ({placeholders})')
            search_params.extend(extra_owner_entity_ids)

        where.append('(' + ' OR '.join(search_terms) + ')')
        params.extend(search_params)

    sql = f'''
        SELECT
            e.entity_id AS id,
            e.name,
            e.source_path AS path,
            e.filename,
            e.owner_entity_id,
            e.display_category,
            e.physical_category,
            e.category_mode,
            e.summary_preview,
            e.updated_at AS mtime,
            e.source_revision,
            CASE
                WHEN e.entity_type = 'world_global' THEN 'global'
                WHEN e.entity_type = 'world_resource' THEN 'resource'
                ELSE 'embedded'
            END AS type,
            CASE
                WHEN e.entity_type = 'world_global' THEN 'global'
                WHEN e.entity_type = 'world_resource' THEN 'resource'
                ELSE 'embedded'
            END AS source_type
        FROM index_entities e
        WHERE {' AND '.join(where)}
        ORDER BY e.sort_mtime DESC, e.sort_name ASC
    '''
    return requested_entity_type, search, sql, where, params


def _run_query(conn, filters, *, literal_only=False):
    requested_entity_type, search, sql, where, params = _build_query_parts(filters, literal_only=literal_only)
    paginate = bool(filters.get('paginate', True))
    query_params = list(params)
    if paginate:
        page_size = int(filters.get('page_size') or 20)
        offset = (int(filters.get('page') or 1) - 1) * page_size
        sql = f'{sql} LIMIT ? OFFSET ?'
        query_params.extend([page_size, offset])

    items = [dict(row) for row in conn.execute(sql, query_params).fetchall()]
    total = conn.execute(
        f"SELECT COUNT(*) FROM index_entities e WHERE {' AND '.join(where)}",
        params,
    ).fetchone()[0]
    return requested_entity_type, search, items, int(total)


def query_worldinfo_index(filters):
    search = str(filters.get('search') or '').strip()
    try:
        with _connect(filters.get('db_path')) as conn:
            requested_entity_type, search, items, total = _run_query(conn, filters, literal_only=False)
            stats_result = _category_stats_metadata(conn, requested_entity_type)
            if stats_result is None:
                all_folders, category_counts, empty_physical_folders, folder_semantics = _fallback_folder_metadata(conn, requested_entity_type)
            else:
                all_folders, category_counts, empty_physical_folders, folder_semantics = stats_result
    except sqlite3.OperationalError as exc:
        if search and _is_malformed_match_error(exc):
            with _connect(filters.get('db_path')) as conn:
                requested_entity_type, _search, items, total = _run_query(conn, filters, literal_only=True)
                stats_result = _category_stats_metadata(conn, requested_entity_type)
                if stats_result is None:
                    all_folders, category_counts, empty_physical_folders, folder_semantics = _fallback_folder_metadata(conn, requested_entity_type)
                else:
                    all_folders, category_counts, empty_physical_folders, folder_semantics = stats_result
        else:
            raise

    return {
        'items': items,
        'total': int(total),
        'all_folders': all_folders,
        'category_counts': category_counts,
        'folder_capabilities': {
            path: {
                **caps,
                'can_delete_physical_folder': path in empty_physical_folders,
            }
            for path, caps in _build_folder_capabilities(all_folders, folder_semantics).items()
        },
    }
