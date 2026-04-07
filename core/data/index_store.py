import json


INDEX_SCHEMA_VERSION = 1


SCHEMA_STATEMENTS = [
    '''
    CREATE TABLE IF NOT EXISTS index_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS index_entities (
        entity_id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        source_path TEXT NOT NULL,
        owner_entity_id TEXT DEFAULT '',
        name TEXT NOT NULL,
        filename TEXT NOT NULL,
        display_category TEXT DEFAULT '',
        physical_category TEXT DEFAULT '',
        category_mode TEXT DEFAULT 'physical',
        favorite INTEGER DEFAULT 0,
        summary_preview TEXT DEFAULT '',
        updated_at REAL DEFAULT 0,
        import_time REAL DEFAULT 0,
        token_count INTEGER DEFAULT 0,
        sort_name TEXT DEFAULT '',
        sort_mtime REAL DEFAULT 0,
        thumb_url TEXT DEFAULT '',
        source_revision TEXT DEFAULT ''
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS index_entity_tags (
        entity_id TEXT NOT NULL,
        tag TEXT NOT NULL,
        PRIMARY KEY (entity_id, tag)
    )
    ''',
    '''
    CREATE VIRTUAL TABLE IF NOT EXISTS index_search_fast USING fts5(
        entity_id UNINDEXED,
        content
    )
    ''',
    '''
    CREATE VIRTUAL TABLE IF NOT EXISTS index_search_full USING fts5(
        entity_id UNINDEXED,
        content
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS index_category_stats (
        scope TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        category_path TEXT NOT NULL,
        direct_count INTEGER NOT NULL DEFAULT 0,
        subtree_count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (scope, entity_type, category_path)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS index_facet_stats (
        scope TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        facet_name TEXT NOT NULL,
        facet_value TEXT NOT NULL,
        facet_count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (scope, entity_type, facet_name, facet_value)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS index_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_type TEXT NOT NULL,
        entity_id TEXT DEFAULT '',
        source_path TEXT DEFAULT '',
        payload_json TEXT DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'pending',
        created_at REAL NOT NULL DEFAULT (strftime('%s', 'now')),
        started_at REAL DEFAULT 0,
        finished_at REAL DEFAULT 0,
        error_msg TEXT DEFAULT ''
    )
    ''',
]


def ensure_index_schema(conn):
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)

    conn.execute(
        'INSERT OR REPLACE INTO index_meta(key, value) VALUES (?, ?)',
        ('schema_version', str(INDEX_SCHEMA_VERSION)),
    )
    conn.execute(
        'INSERT OR IGNORE INTO index_meta(key, value) VALUES (?, ?)',
        (
            'build_state',
            json.dumps({'state': 'empty', 'scope': 'cards', 'progress': 0, 'message': ''}),
        ),
    )
    conn.commit()
