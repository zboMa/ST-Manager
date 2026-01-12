import os
import json
import time
import shutil
import logging
import sqlite3
from io import BytesIO
from flask import Blueprint, request, jsonify, send_file

# === 基础设施 ===
from core.config import BASE_DIR, load_config, DEFAULT_DB_PATH, CARDS_FOLDER, TRASH_FOLDER 
from core.context import ctx
from core.data.db_session import get_db
from core.data.ui_store import load_ui_data, UI_DATA_FILE
from core.services.cache_service import invalidate_wi_list_cache
from core.utils.filesystem import safe_move_to_trash

def _safe_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path) if path and os.path.exists(path) else 0.0
    except:
        return 0.0

# === 工具函数 ===
from core.utils.image import extract_card_info # 用于 export logic

logger = logging.getLogger(__name__)

bp = Blueprint('wi', __name__)

@bp.route('/api/world_info/list', methods=['GET'])
def api_list_world_infos():
    try:
        search = request.args.get('search', '').lower().strip()
        wi_type = request.args.get('type', 'all') # all, global, resource, embedded

        # 新增分页参数
        try:
            page = int(request.args.get('page', 1))
            page_size = int(request.args.get('page_size', 20))
        except:
            page, page_size = 1, 20

        # === 动态获取配置中的路径，而不是使用全局静态变量 ===
        cfg = load_config()
        raw_wi_dir = cfg.get('world_info_dir', 'lorebooks')
        if os.path.isabs(raw_wi_dir):
            current_wi_folder = raw_wi_dir
        else:
            current_wi_folder = os.path.join(BASE_DIR, raw_wi_dir)
            
        if not os.path.exists(current_wi_folder):
            try: os.makedirs(current_wi_folder)
            except: pass
        
        # ===== [CACHE] key = type + search（未分页 items）=====
        cache_key = f"{wi_type}||{search}"

        cfg = load_config()
        default_res_dir = os.path.join(BASE_DIR, cfg.get('resources_dir', 'resources'))
        db_path = DEFAULT_DB_PATH

        global_dir_sig   = _safe_mtime(current_wi_folder)
        resource_dir_sig = _safe_mtime(default_res_dir)
        ui_data_sig      = _safe_mtime(UI_DATA_FILE)
        db_sig           = _safe_mtime(db_path)

        if wi_type == 'global':
            sig = ('global', global_dir_sig)
        elif wi_type == 'resource':
            sig = ('resource', resource_dir_sig, ui_data_sig)
        elif wi_type == 'embedded':
            sig = ('embedded', db_sig)
        else:  # all
            sig = ('all', global_dir_sig, resource_dir_sig, ui_data_sig, db_sig)

        cached_items = None
        with ctx.wi_list_cache_lock:
            cached = ctx.wi_list_cache.get(cache_key)
            if cached and cached.get("sig") == sig:
                items = cached.get("items") or []
                # === 命中缓存直接分页返回，不再往下扫描 ===
                total_count = len(items)
                start = (page - 1) * page_size
                end = start + page_size
                return jsonify({
                    "success": True,
                    "items": items[start:end],
                    "total": total_count,
                    "page": page,
                    "page_size": page_size
                })

        # 原扫描
        items = []

        # 1. 全局目录 (Global)
        if wi_type in ['all', 'global']:
            for root, dirs, files in os.walk(current_wi_folder):
                for f in files:
                    if f.lower().endswith('.json'):
                        full_path = os.path.join(root, f)
                        try:
                            if os.path.getsize(full_path) == 0: continue
                            # 简单读取 header，不读取全部 entries 以优化性能
                            # 如果文件巨大，可以考虑只读前几KB解析
                            with open(full_path, 'r', encoding='utf-8') as f_obj:
                                data = json.load(f_obj)
                                # 兼容 list 或 dict
                                file_name = os.path.basename(f)
                                base_name = os.path.splitext(file_name)[0]
                                name_source = "filename"
                                if isinstance(data, dict):
                                    name_val = (data.get('name') or "").strip()
                                    if name_val:
                                        name = name_val
                                        name_source = "meta"
                                    else:
                                        name = file_name  # 显示含扩展名，更像“文件”
                                else:
                                    name = file_name
                                    
                                items.append({
                                    "id": f"global::{os.path.relpath(full_path, current_wi_folder)}",
                                    "type": "global",
                                    "name": name,
                                    "name_source": name_source,
                                    "file_name": file_name,
                                    "path": full_path,
                                    "mtime": os.path.getmtime(full_path)
                                })
                        except Exception as e: 
                            print(f"Error reading WI {f}: {e}")
                            continue

        # 2. 资源目录 (Resource) - 基于 ui_data 查找自定义路径
        if wi_type in ['all', 'resource']:
            ui_data = load_ui_data()
            cfg = load_config()
            default_res_dir = os.path.join(BASE_DIR, cfg.get('resources_dir', 'resources'))
            
            # 建立 card_id -> resource_path 的映射
            # 此时我们要扫描的是哪些文件夹里有 'lorebooks/*.json'
            # 为了避免重复扫描同一个文件夹（多个卡片可能指向同一个资源目录），我们需要去重
            scanned_paths = set()
            
            # 遍历所有卡片(从缓存)来获取它们的资源目录配置
            # 如果缓存没加载，先加载
            if not ctx.cache.initialized: ctx.cache.reload_from_db()
            
            for card in ctx.cache.cards:
                # 获取该卡片的资源目录设置
                # 优先从 card 对象读取(如果 reload_from_db 已经注入)，否则从 ui_data 查
                # 假设 ui_data key 是 card.id 或 bundle_dir
                key = card.get('bundle_dir') if card.get('is_bundle') else card['id']
                ui_info = ui_data.get(key, {})
                res_folder = ui_info.get('resource_folder') or card.get('resource_folder')
                
                if not res_folder: continue
                
                # 解析绝对路径
                if os.path.isabs(res_folder):
                    target_dir = res_folder
                else:
                    target_dir = os.path.join(default_res_dir, res_folder)
                
                # 目标：该资源目录下的 lorebooks 子文件夹
                lore_dir = os.path.join(target_dir, 'lorebooks')
                
                if lore_dir in scanned_paths: continue # 已扫描过
                scanned_paths.add(lore_dir)
                
                if os.path.exists(lore_dir):
                    for f in os.listdir(lore_dir):
                        if f.lower().endswith('.json'):
                            full_path = os.path.join(lore_dir, f)
                            try:
                                with open(full_path, 'r', encoding='utf-8') as f_obj:
                                    data = json.load(f_obj)
                                    file_name = os.path.basename(f)
                                    base_name = os.path.splitext(file_name)[0]
                                    name_source = "filename"
                                    if isinstance(data, dict):
                                        name_val = (data.get('name') or "").strip()
                                        if name_val:
                                            name = name_val
                                            name_source = "meta"
                                        else:
                                            name = file_name
                                    else:
                                        name = file_name
                                    items.append({
                                        "id": f"resource::{key}::{f}",
                                        "type": "resource",
                                        "name": name,
                                        "name_source": name_source,
                                        "file_name": file_name,
                                        "path": full_path,
                                        "card_name": card['char_name'], # 关联的角色名
                                        "card_id": card['id'], # 用于跳转
                                        "mtime": os.path.getmtime(full_path)
                                    })
                            except: continue

        # 3. 角色卡内嵌 (Embedded) - 查询数据库
        if wi_type in ['all', 'embedded']:
            conn = get_db()
            cursor = conn.execute("SELECT id, char_name, character_book_name, last_modified FROM card_metadata WHERE has_character_book = 1")
            rows = cursor.fetchall()
            for row in rows:
                items.append({
                    "id": f"embedded::{row['id']}",
                    "type": "embedded",
                    "name": row['character_book_name'] or f"{row['char_name']}'s WI",
                    "card_name": row['char_name'],
                    "card_id": row['id'],
                    "mtime": row['last_modified']
                })

        # 过滤与排序
        if search:
            items = [i for i in items if search in i['name'].lower() or (i.get('card_name') and search in i['card_name'].lower())]
            
        items.sort(key=lambda x: x.get('mtime', 0), reverse=True)

        # ===== [CACHE WRITE] 只在未命中缓存时写入 =====
        if cached_items is None:
            with ctx.wi_list_cache_lock:
                # 简单上限，避免 key 太多（比如用户疯狂换 search）
                if len(ctx.wi_list_cache) > 200:
                    ctx.wi_list_cache.clear()
                ctx.wi_list_cache[cache_key] = {"sig": sig, "items": items, "ts": time.time()}

        # 分页切片
        total_count = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_items = items[start:end]
        
        return jsonify({
            "success": True, 
            "items": paginated_items, 
            "total": total_count,
            "page": page,
            "page_size": page_size
        })
    except Exception as e:
        logger.error(f"List WI error: {e}")
        return jsonify({"success": False, "msg": str(e)})

# 上传世界书
@bp.route('/api/upload_world_info', methods=['POST'])
def api_upload_world_info():
    try:
        files = request.files.getlist('files')
        if not files:
            return jsonify({"success": False, "msg": "未接收到文件"})

        # 获取全局世界书目录
        cfg = load_config()
        raw_wi_dir = cfg.get('world_info_dir', 'lorebooks')
        target_dir = raw_wi_dir if os.path.isabs(raw_wi_dir) else os.path.join(BASE_DIR, raw_wi_dir)
        
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        success_count = 0
        failed_list = []

        for file in files:
            if not file.filename.lower().endswith('.json'):
                failed_list.append(file.filename)
                continue
            
            # 防重名
            safe_name = os.path.basename(file.filename)
            name_part, ext = os.path.splitext(safe_name)
            save_path = os.path.join(target_dir, safe_name)
            
            counter = 1
            while os.path.exists(save_path):
                save_path = os.path.join(target_dir, f"{name_part}_{counter}{ext}")
                counter += 1
            
            try:
                # 尝试验证 JSON 格式
                content = file.read()
                json.loads(content) # 校验格式
                
                # 重置指针并保存
                file.seek(0)
                file.save(save_path)
                success_count += 1
            except Exception:
                failed_list.append(file.filename)

        msg = f"成功上传 {success_count} 个世界书。"
        if failed_list:
            msg += f" 失败: {', '.join(failed_list)}"
        invalidate_wi_list_cache()
        return jsonify({"success": True, "count": success_count, "msg": msg})
        
    except Exception as e:
        logger.error(f"Upload WI error: {e}")
        return jsonify({"success": False, "msg": str(e)})

@bp.route('/api/world_info/detail', methods=['POST'])
def api_get_world_info_detail():
    try:
        # id 格式: "type::path"
        wi_id = request.json.get('id')
        source_type = request.json.get('source_type')
        file_path = request.json.get('file_path')
        
        if not os.path.exists(file_path):
             return jsonify({"success": False, "msg": "文件不存在"})
             
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)})

@bp.route('/api/world_info/save', methods=['POST'])
def api_save_world_info():
    try:
        save_mode = request.json.get('save_mode') # 'overwrite', 'new_global', 'new_resource'
        target_path = request.json.get('file_path') # 如果是 overwrite
        name = request.json.get('name')
        content = request.json.get('content') # JSON 对象
        
        final_path = ""
        
        if save_mode == 'overwrite':
            if not target_path or not os.path.exists(target_path):
                return jsonify({"success": False, "msg": "目标文件不存在，无法覆盖"})
            final_path = target_path
            
        elif save_mode == 'new_global':
            cfg = load_config()
            raw_wi = cfg.get('world_info_dir', 'lorebooks')
            current_wi_folder = raw_wi if os.path.isabs(raw_wi) else os.path.join(BASE_DIR, raw_wi)
            if not os.path.exists(current_wi_folder): os.makedirs(current_wi_folder)
            # 保存到全局目录
            filename = f"{name}.json".replace('/', '_').replace('\\', '_')
            final_path = os.path.join(current_wi_folder, filename)
            # 防重名
            counter = 1
            base, ext = os.path.splitext(final_path)
            while os.path.exists(final_path):
                final_path = f"{base}_{counter}{ext}"
                counter += 1
        
        elif save_mode == 'new_resource':
            # 保存到指定角色的资源目录
            card_id = request.json.get('card_id')
            # 获取资源目录
            ui_data = load_ui_data()
            # ... (获取资源路径逻辑) ...
            # 略，需要复用 get_resource_folder 逻辑
            pass 

        # 写入
        compact = bool(request.json.get('compact', False))
        with open(final_path, 'w', encoding='utf-8') as f:
            if compact:
                json.dump(content, f, ensure_ascii=False, separators=(',', ':'))
            else:
                json.dump(content, f, ensure_ascii=False, indent=2)
        
        invalidate_wi_list_cache()
        return jsonify({"success": True, "new_path": final_path})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)})

@bp.route('/api/tools/migrate_lorebooks', methods=['POST'])
def api_migrate_lorebooks():
    """
    一键整理：遍历所有卡片的资源目录，将根目录下的 json 世界书移动到 lorebooks 子目录
    """
    try:
        cfg = load_config()
        default_res_dir = os.path.join(BASE_DIR, cfg.get('resources_dir', 'resources'))
        ui_data = load_ui_data()
        
        # 获取所有涉及的资源目录路径 (去重)
        target_res_dirs = set()
        
        # 1. 扫描 resources/ 根目录下的文件夹
        if os.path.exists(default_res_dir):
            for d in os.listdir(default_res_dir):
                full = os.path.join(default_res_dir, d)
                if os.path.isdir(full): target_res_dirs.add(full)

        # 2. 扫描卡片指定的自定义路径
        if not ctx.cache.initialized: ctx.cache.reload_from_db()
        for card in ctx.cache.cards:
            res_folder = card.get('resource_folder')
            if not res_folder:
                # 尝试从 ui_data 获取
                key = card.get('bundle_dir') if card.get('is_bundle') else card['id']
                res_folder = ui_data.get(key, {}).get('resource_folder')
            
            if res_folder:
                if os.path.isabs(res_folder):
                    if os.path.exists(res_folder): target_res_dirs.add(res_folder)
                else:
                    full = os.path.join(default_res_dir, res_folder)
                    if os.path.exists(full): target_res_dirs.add(full)

        moved_count = 0
        
        for res_path in target_res_dirs:
            lore_target_dir = os.path.join(res_path, 'lorebooks')
            
            # 扫描该资源目录根下的文件
            try:
                files = os.listdir(res_path)
            except:
                continue

            for f in files:
                if f.lower().endswith('.json'):
                    src_path = os.path.join(res_path, f)
                    if not os.path.isfile(src_path): continue

                    # 检查是否为有效 WI
                    try:
                        with open(src_path, 'r', encoding='utf-8') as f_obj:
                            try:
                                data = json.load(f_obj)
                            except: continue # JSON 解析失败跳过

                            is_wi = False
                            # 判定标准
                            if isinstance(data, dict) and 'entries' in data: is_wi = True
                            elif isinstance(data, list) and len(data) > 0:
                                # 检查第一项是否有 keys 或 key，防止把其他配置json误判
                                first = data[0]
                                if isinstance(first, dict) and ('keys' in first or 'key' in first):
                                    is_wi = True
                            
                            if is_wi:
                                if not os.path.exists(lore_target_dir):
                                    os.makedirs(lore_target_dir)
                                
                                dst_path = os.path.join(lore_target_dir, f)
                                # 防重名
                                if os.path.exists(dst_path):
                                    if os.path.samefile(src_path, dst_path): continue
                                    base, ext = os.path.splitext(f)
                                    dst_path = os.path.join(lore_target_dir, f"{base}_{int(time.time())}{ext}")
                                
                                # 执行移动
                                try:
                                    # 1. 尝试移动
                                    shutil.move(src_path, dst_path)               
                                    moved_count += 1
                                except Exception as move_err:
                                    print(f"Move failed for {f}: {move_err}")
                                    # 尝试回滚或忽略，防止数据丢失
                                    continue
                    except Exception as e:
                        print(f"Error checking file {src_path}: {e}")
                        continue
        
        invalidate_wi_list_cache()
        return jsonify({"success": True, "count": moved_count})
    except Exception as e:
        logger.error(f"Migrate error: {e}")
        return jsonify({"success": False, "msg": str(e)})

@bp.route('/api/export_worldbook_single', methods=['POST'])
def api_export_worldbook_single():
    try:
        cid = request.json.get("card_id")
        if not cid:
            return jsonify({"success": False, "msg": "角色卡ID缺失"})

        rel = cid.replace('/', os.sep)
        file_path = os.path.join(CARDS_FOLDER, rel)
        if not os.path.exists(file_path):
            return jsonify({"success": False, "msg": "未找到角色卡"})

        info = extract_card_info(file_path)
        if not info:
            return jsonify({"success": False, "msg": "未找到元数据"})

        # 获取世界书数据
        book = info.get("data", {}).get("character_book") or info.get("character_book")
        if not book:
            return jsonify({"success": False, "msg": "角色卡无世界书"})

        # === 数据源获取 ===
        entries_raw = []
        if isinstance(book, list):
            entries_raw = book
        elif isinstance(book, dict):
            if 'entries' in book:
                if isinstance(book['entries'], list):
                    entries_raw = book['entries']
                elif isinstance(book['entries'], dict):
                    entries_raw = list(book['entries'].values())
        
        # === 增量导出逻辑 (Pass-through) ===
        export_entries = {}
        for idx, entry in enumerate(entries_raw):
            # 1. 【关键】复制原始数据，保留所有未知字段 (如 vectorized, depth 等)
            final_entry = entry.copy()
            
            # 2. 更新/标准化 ST 核心字段
            # 我们内部使用 keys(复数)/enabled(正向)，ST 使用 key(单数)/disable(反向)
            
            # UID 重置为索引
            final_entry['uid'] = idx
            final_entry['displayIndex'] = idx
            
            # 关键字映射: keys -> key
            # 优先使用内部的 keys，如果没有则保留原有的 key
            if 'keys' in entry:
                final_entry['key'] = entry['keys']
            if 'key' not in final_entry:
                final_entry['key'] = []

            # 次要关键字映射
            if 'secondary_keys' in entry:
                final_entry['keysecondary'] = entry['secondary_keys']
            if 'keysecondary' not in final_entry:
                final_entry['keysecondary'] = []

            # 启用状态映射: enabled -> disable
            is_enabled = entry.get('enabled', not entry.get('disable', False))
            final_entry['disable'] = not is_enabled
            
            # 权重映射: insertion_order -> order
            if 'insertion_order' in entry:
                final_entry['order'] = entry['insertion_order']
            
            # 移除我们内部使用的临时字段 (可选，为了保持 JSON 整洁)
            final_entry.pop('enabled', None)
            final_entry.pop('keys', None)
            final_entry.pop('secondary_keys', None)
            final_entry.pop('insertion_order', None)

            export_entries[str(idx)] = final_entry

        final_export = {
            "entries": export_entries,
            "name": book.get('name', 'World Info') if isinstance(book, dict) else "World Info"
        }
        
        # 保留原始书的其他顶层属性 (如 description 等，如果有的话)
        if isinstance(book, dict):
            for k, v in book.items():
                if k not in ['entries', 'name']:
                    final_export[k] = v

        json_bytes = json.dumps(final_export, ensure_ascii=False, indent=2).encode("utf-8")
        buf = BytesIO(json_bytes)
        buf.seek(0)

        return send_file(
            buf,
            mimetype="application/json; charset=utf-8",
            as_attachment=True,
            download_name=f"{cid.replace('/', '_')}_worldbook.json"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})

# --- WI Clipboard APIs ---
@bp.route('/api/wi/clipboard/list', methods=['GET'])
def api_wi_clipboard_list():
    try:
        db_path = DEFAULT_DB_PATH
        with sqlite3.connect(db_path, timeout=10) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM wi_clipboard ORDER BY sort_order ASC, created_at DESC")
            rows = cursor.fetchall()
            items = []
            for r in rows:
                items.append({
                    "db_id": r['id'],
                    "content": json.loads(r['content_json']),
                    "sort_order": r['sort_order']
                })
        return jsonify({"success": True, "items": items})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)})

@bp.route('/api/wi/clipboard/add', methods=['POST'])
def api_wi_clipboard_add():
    try:
        entry = request.json.get('entry')
        overwrite_id = request.json.get('overwrite_id') # 如果有值，则是覆盖操作
        limit = 50 # 限制数量

        db_path = DEFAULT_DB_PATH
        with sqlite3.connect(db_path, timeout=10) as conn:
            cursor = conn.cursor()
            
            # 覆盖模式
            if overwrite_id:
                cursor.execute("UPDATE wi_clipboard SET content_json = ?, created_at = ? WHERE id = ?", 
                              (json.dumps(entry), time.time(), overwrite_id))
                conn.commit()
                return jsonify({"success": True, "msg": "已覆盖条目"})

            # 新增模式：检查数量
            cursor.execute("SELECT COUNT(*) FROM wi_clipboard")
            count = cursor.fetchone()[0]
            if count >= limit:
                return jsonify({"success": False, "code": "FULL", "msg": "剪切板已满"})
            
            # 获取最大排序
            cursor.execute("SELECT MAX(sort_order) FROM wi_clipboard")
            max_order = cursor.fetchone()[0]
            new_order = (max_order if max_order is not None else 0) + 1

            cursor.execute("INSERT INTO wi_clipboard (content_json, sort_order, created_at) VALUES (?, ?, ?)",
                           (json.dumps(entry), new_order, time.time()))
            conn.commit()
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)})

@bp.route('/api/wi/clipboard/delete', methods=['POST'])
def api_wi_clipboard_delete():
    try:
        db_id = request.json.get('db_id')
        db_path = DEFAULT_DB_PATH
        with sqlite3.connect(db_path, timeout=10) as conn:
            conn.execute("DELETE FROM wi_clipboard WHERE id = ?", (db_id,))
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)})

@bp.route('/api/wi/clipboard/clear', methods=['POST'])
def api_wi_clipboard_clear():
    try:
        db_path = DEFAULT_DB_PATH
        with sqlite3.connect(db_path, timeout=10) as conn:
            conn.execute("DELETE FROM wi_clipboard")
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)})

@bp.route('/api/wi/clipboard/reorder', methods=['POST'])
def api_wi_clipboard_reorder():
    try:
        order_map = request.json.get('order_map') # list of db_ids in order
        db_path = DEFAULT_DB_PATH
        with sqlite3.connect(db_path, timeout=10) as conn:
            for idx, db_id in enumerate(order_map):
                conn.execute("UPDATE wi_clipboard SET sort_order = ? WHERE id = ?", (idx, db_id))
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)})
    
# 删除世界书
@bp.route('/api/world_info/delete', methods=['POST'])
def api_delete_world_info():
    try:
        # 传入完整文件路径
        file_path = request.json.get('file_path')
        
        if not file_path or not os.path.exists(file_path):
            return jsonify({"success": False, "msg": "文件不存在或路径为空"})
            
        # 简单的安全检查，防止删除系统关键文件
        if 'card_metadata' in file_path or 'config.json' in file_path:
             return jsonify({"success": False, "msg": "非法操作：禁止删除系统文件"})

        # 执行移动到回收站
        if safe_move_to_trash(file_path, TRASH_FOLDER):
            # 刷新列表缓存
            invalidate_wi_list_cache()
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "msg": "移动到回收站失败"})
            
    except Exception as e:
        logger.error(f"Delete WI error: {e}")
        return jsonify({"success": False, "msg": str(e)})