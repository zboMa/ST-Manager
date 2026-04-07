import sqlite3

from core.config import DEFAULT_DB_PATH


def _is_malformed_match_error(exc):
    message = str(exc or '').lower()
    malformed_markers = (
        'fts5: syntax error',
        'unterminated string',
        'malformed match expression',
    )
    return any(marker in message for marker in malformed_markers)


def _connect(db_path=None):
    conn = sqlite3.connect(db_path or DEFAULT_DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def query_indexed_cards(filters):
    where = ["e.entity_type = 'card'"]
    params = []
    search_scope = str(filters.get('search_scope') or 'current').strip().lower()

    category = str(filters.get('category') or '').strip()
    if category:
        where.append('(e.display_category = ? OR e.display_category LIKE ?)')
        params.extend([category, f'{category}/%'])

    if search_scope != 'full':
        if filters.get('fav_filter') == 'included':
            where.append('e.favorite = 1')
        elif filters.get('fav_filter') == 'excluded':
            where.append('e.favorite = 0')

        include_tags = [tag for tag in filters.get('include_tags', []) if tag]
        for tag in include_tags:
            where.append(
                'EXISTS (SELECT 1 FROM index_entity_tags t WHERE t.entity_id = e.entity_id AND t.tag = ?)'
            )
            params.append(tag)

        exclude_tags = [tag for tag in filters.get('exclude_tags', []) if tag]
        for tag in exclude_tags:
            where.append(
                'NOT EXISTS (SELECT 1 FROM index_entity_tags t WHERE t.entity_id = e.entity_id AND t.tag = ?)'
            )
            params.append(tag)

    token_min = filters.get('token_min')
    if token_min is not None:
        where.append('COALESCE(e.token_count, 0) >= ?')
        params.append(int(token_min))

    token_max = filters.get('token_max')
    if token_max is not None:
        where.append('COALESCE(e.token_count, 0) <= ?')
        params.append(int(token_max))

    search = str(filters.get('search') or '').strip()
    if search:
        if filters.get('search_mode') == 'fulltext':
            where.append(
                'e.entity_id IN (SELECT entity_id FROM index_search_full WHERE index_search_full MATCH ?)'
            )
            params.append(search)
        else:
            where.append(
                'e.entity_id IN (SELECT entity_id FROM index_search_fast WHERE content LIKE ? ESCAPE \'\\\')'
            )
            escaped = search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            params.append(f'%{escaped}%')

    sql = f'''
        SELECT
            substr(e.entity_id, 7) AS id,
            e.name AS char_name,
            e.filename,
            e.display_category AS category,
            e.favorite AS is_favorite,
            e.summary_preview AS ui_summary,
            e.updated_at AS last_modified,
            e.import_time,
            e.token_count,
            e.thumb_url,
            e.source_revision
        FROM index_entities e
        WHERE {' AND '.join(where)}
        ORDER BY e.sort_mtime DESC, e.sort_name ASC
        LIMIT ? OFFSET ?
    '''
    page_size = int(filters.get('page_size') or 20)
    offset = (int(filters.get('page') or 1) - 1) * page_size
    db_path = filters.get('db_path')

    try:
        with _connect(db_path) as conn:
            rows = conn.execute(sql, [*params, page_size, offset]).fetchall()
            total = conn.execute(
                f"SELECT COUNT(*) FROM index_entities e WHERE {' AND '.join(where)}",
                params,
            ).fetchone()[0]
    except sqlite3.OperationalError as exc:
        # FTS MATCH rejects some malformed-but-plausible user input such as bare quotes.
        if search and _is_malformed_match_error(exc):
            return {
                'cards': [],
                'total_count': 0,
            }
        raise

    return {
        'cards': [dict(row) for row in rows],
        'total_count': int(total),
    }
