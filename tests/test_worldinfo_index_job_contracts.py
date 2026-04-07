from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def test_cards_api_update_paths_enqueue_worldinfo_owner_refresh():
    source = _read('core/api/v1/cards.py')

    assert "cache_updated = update_card_cache(final_rel_path_id, current_full_path, parsed_info=info, mtime=current_mtime)" in source
    assert "if cache_updated:\n            enqueue_index_job('upsert_world_owner', entity_id=final_rel_path_id, source_path=current_full_path)" in source
    assert "cache_updated = update_card_cache(rel_path, target_save_path)" in source
    assert "if cache_updated:\n            enqueue_index_job('upsert_world_owner', entity_id=rel_path, source_path=target_save_path)" in source
    assert "cache_updated = update_card_cache(final_id, target_save_path)" in source
    assert "if cache_updated:\n            enqueue_index_job('upsert_world_owner', entity_id=final_id, source_path=target_save_path)" in source
    assert "cache_updated = update_card_cache(rel_id, dst_path, parsed_info=info, file_hash=final_hash, file_size=final_size, mtime=mtime)" in source
    assert "if cache_updated:\n                enqueue_index_job('upsert_world_owner', entity_id=rel_id, source_path=dst_path)" in source
