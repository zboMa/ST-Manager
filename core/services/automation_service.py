import logging
import os
from core.config import load_config
from core.automation.manager import rule_manager
from core.automation.engine import AutomationEngine
from core.automation.executor import AutomationExecutor
from core.automation.constants import (
    ACT_FETCH_FORUM_TAGS,
    ACT_MERGE_TAGS,
    ACT_SET_CHAR_NAME_FROM_FILENAME,
    ACT_SET_WI_NAME_FROM_FILENAME,
    ACT_SET_FILENAME_FROM_CHAR_NAME,
    ACT_SET_FILENAME_FROM_WI_NAME,
)
from core.automation.tag_merge import apply_merge_actions_to_tags
from core.context import ctx
from core.data.ui_store import load_ui_data
from core.services.card_service import resolve_ui_key
from core.utils.tag_parser import split_action_tags

logger = logging.getLogger(__name__)

engine = AutomationEngine()
executor = AutomationExecutor()


def _build_runtime_from_active_ruleset():
    cfg = load_config()
    active_id = cfg.get('active_automation_ruleset')

    if not active_id:
        return None

    ruleset = rule_manager.get_ruleset(active_id)
    if not ruleset:
        return None

    return {
        'ruleset_id': active_id,
        'ruleset': ruleset,
        'slash_as_separator': bool(cfg.get('automation_slash_is_tag_separator', False))
    }


def get_global_tag_merge_runtime():
    """
    获取全局规则集中的标签合并运行时上下文。
    返回 None 表示未启用全局规则集或规则集不存在。
    """
    try:
        return _build_runtime_from_active_ruleset()
    except Exception as e:
        logger.error(f"Build global tag merge runtime error: {e}")
        return None


def auto_run_tag_merge_on_tagging(card_id, tags, ui_data=None, runtime=None):
    """
    在“手动打标”场景下应用全局规则集里的 merge_tags 动作。
    典型触发点：批量标签管理、详情页编辑标签并保存。
    """
    try:
        rt = runtime or _build_runtime_from_active_ruleset()
        if not rt:
            return None

        ruleset = rt.get('ruleset')
        if not ruleset:
            return None

        slash_as_separator = bool(rt.get('slash_as_separator', False))

        card_obj = ctx.cache.id_map.get(card_id)
        if not card_obj:
            parent_dir = os.path.dirname(card_id).replace('\\', '/')
            bundle_main_id = ctx.cache.bundle_map.get(parent_dir)
            if bundle_main_id:
                card_obj = ctx.cache.id_map.get(bundle_main_id)

        if not card_obj:
            logger.debug(f"Tag merge skipped, card not found in cache: {card_id}")
            return None

        if ui_data is None:
            ui_data = load_ui_data()

        context_data = dict(card_obj)
        context_data['tags'] = list(tags or [])

        ui_key = resolve_ui_key(card_id)
        ui_info = ui_data.get(ui_key, {})
        context_data['ui_summary'] = ui_info.get('summary', '')
        context_data['source_link'] = ui_info.get('link', '')

        plan_raw = engine.evaluate(context_data, ruleset, match_if_no_conditions=True)
        merge_actions = [
            act for act in plan_raw.get('actions', [])
            if isinstance(act, dict) and act.get('type') == ACT_MERGE_TAGS
        ]

        if not merge_actions:
            return {
                'run': True,
                'actions': 0,
                'result': {
                    'tags': list(tags or []),
                    'changed': False,
                    'replacements': [],
                    'replace_rules': {}
                }
            }

        merge_result = apply_merge_actions_to_tags(
            tags,
            merge_actions,
            slash_as_separator=slash_as_separator
        )

        return {
            'run': True,
            'actions': len(merge_actions),
            'result': merge_result
        }
    except Exception as e:
        logger.error(f"Auto-run tag merge error: {e}")
        return None

def auto_run_rules_on_card(card_id):
    """
    检查是否有全局激活的规则集，如果有，对指定卡片运行。
    用于上传/导入后的钩子。
    """
    try:
        cfg = load_config()
        active_id = cfg.get('active_automation_ruleset')
        
        if not active_id:
            return None # 未开启自动化
            
        ruleset = rule_manager.get_ruleset(active_id)
        if not ruleset:
            return None

        slash_as_separator = bool(cfg.get('automation_slash_is_tag_separator', False))
            
        # 获取卡片数据
        # 刚上传的卡片可能还没进缓存（如果是并发情况），但通常 API 也就是串行的
        # 我们尝试从缓存拿，如果没有，尝试等待一下或者重新读 DB (略重)
        # 这里假设调用时，update_card_cache 已经执行，缓存已更新
        
        card_obj = ctx.cache.id_map.get(card_id)
        if not card_obj:
            logger.warning(f"Auto-run: Card {card_id} not found in cache immediately.")
            return None
            
        # 准备数据
        ui_data = load_ui_data()
        context_data = dict(card_obj)
        ui_key = resolve_ui_key(card_id)
        ui_info = ui_data.get(ui_key, {})
        context_data['ui_summary'] = ui_info.get('summary', '')
        
        # 评估（自动执行时，无条件的规则也应执行）
        plan_raw = engine.evaluate(context_data, ruleset, match_if_no_conditions=True)
        
        if not plan_raw['actions']:
            return {"run": True, "actions": 0}
            
        # 转换 Plan
        exec_plan = {
            'move': None,
            'add_tags': set(),
            'remove_tags': set(),
            'favorite': None,
            'fetch_forum_tags': None,
            'set_char_name_from_filename': False,
            'set_wi_name_from_filename': False,
            'set_filename_from_char_name': False,
            'set_filename_from_wi_name': False,
        }
        for act in plan_raw['actions']:
            t = act['type']
            v = act.get('value')
            if t == 'move_folder':
                exec_plan['move'] = v
            elif t == 'add_tag':
                exec_plan['add_tags'].update(split_action_tags(v, slash_as_separator=slash_as_separator))
            elif t == 'remove_tag':
                exec_plan['remove_tags'].update(split_action_tags(v, slash_as_separator=slash_as_separator))
            elif t == 'set_favorite':
                exec_plan['favorite'] = (str(v).lower() == 'true')
            elif t == ACT_SET_CHAR_NAME_FROM_FILENAME:
                exec_plan['set_char_name_from_filename'] = True
            elif t == ACT_SET_WI_NAME_FROM_FILENAME:
                exec_plan['set_wi_name_from_filename'] = True
            elif t == ACT_SET_FILENAME_FROM_CHAR_NAME:
                exec_plan['set_filename_from_char_name'] = True
            elif t == ACT_SET_FILENAME_FROM_WI_NAME:
                exec_plan['set_filename_from_wi_name'] = True
            elif t == ACT_FETCH_FORUM_TAGS:
                # 导入时跳过论坛标签抓取，因为此时 URL 为空
                # 此动作仅在用户更新来源链接时触发
                continue
            elif t == ACT_MERGE_TAGS:
                # 标签合并仅在手动打标场景触发，导入时跳过
                continue
            
        # 执行
        res = executor.apply_plan(card_id, exec_plan, ui_data)

        logger.info(f"Auto-run applied on {card_id}: {res}")
        return {"run": True, "result": res}

    except Exception as e:
        logger.error(f"Auto-run error: {e}")
        return None


def auto_run_forum_tags_on_link_update(card_id):
    """
    当卡片超链接更新时，仅执行抓取论坛标签动作。
    用于用户在卡片详情页更新来源链接后的钩子。
    """
    try:
        cfg = load_config()
        active_id = cfg.get('active_automation_ruleset')

        if not active_id:
            return None  # 未开启自动化

        ruleset = rule_manager.get_ruleset(active_id)
        if not ruleset:
            return None

        # 获取卡片数据
        card_obj = ctx.cache.id_map.get(card_id)
        if not card_obj:
            logger.warning(f"Auto-run forum tags: Card {card_id} not found in cache.")
            return None

        # 准备数据
        ui_data = load_ui_data()
        context_data = dict(card_obj)
        ui_key = resolve_ui_key(card_id)
        ui_info = ui_data.get(ui_key, {})
        context_data['ui_summary'] = ui_info.get('summary', '')

        # 评估（自动执行时，无条件的规则也应执行）
        plan_raw = engine.evaluate(context_data, ruleset, match_if_no_conditions=True)

        if not plan_raw['actions']:
            return {"run": True, "actions": 0}

        # 只提取 fetch_forum_tags 动作
        fetch_forum_tags_config = None
        for act in plan_raw['actions']:
            if act['type'] == ACT_FETCH_FORUM_TAGS:
                v = act.get('value')
                if isinstance(v, dict):
                    fetch_forum_tags_config = v
                else:
                    fetch_forum_tags_config = {}
                break  # 只执行第一个抓取论坛标签动作

        if not fetch_forum_tags_config:
            return {"run": True, "actions": 0, "reason": "no_fetch_forum_tags_action"}

        # 构建只包含 fetch_forum_tags 的执行计划
        exec_plan = {
            'move': None,
            'add_tags': set(),
            'remove_tags': set(),
            'favorite': None,
            'fetch_forum_tags': fetch_forum_tags_config,
            'set_char_name_from_filename': False,
            'set_wi_name_from_filename': False,
            'set_filename_from_char_name': False,
            'set_filename_from_wi_name': False,
        }

        # 执行
        res = executor.apply_plan(card_id, exec_plan, ui_data)

        # 抓取论坛标签后，联动执行标签合并（如果全局规则中配置了 merge_tags）
        current_card = ctx.cache.id_map.get(card_id)
        final_tags = list((current_card or {}).get('tags') or res.get('tags_added') or [])
        tag_merge = None

        if final_tags:
            merge_res = auto_run_tag_merge_on_tagging(card_id, final_tags, ui_data=ui_data, runtime={
                'ruleset_id': active_id,
                'ruleset': ruleset,
                'slash_as_separator': bool(cfg.get('automation_slash_is_tag_separator', False))
            })
            merge_payload = (merge_res or {}).get('result') or {}

            if merge_payload.get('changed'):
                merged_tags = merge_payload.get('tags') or final_tags
                if merged_tags != final_tags:
                    from core.services.card_service import modify_card_attributes_internal

                    remove_tags = [t for t in final_tags if t not in merged_tags]
                    add_tags = [t for t in merged_tags if t not in final_tags]
                    if add_tags or remove_tags:
                        ok = modify_card_attributes_internal(card_id, add_tags=add_tags, remove_tags=remove_tags)
                        if ok:
                            final_tags = list(merged_tags)

            if merge_res and int(merge_res.get('actions') or 0) > 0:
                tag_merge = {
                    'triggered': True,
                    'changed': bool(merge_payload.get('changed')),
                    'replacements': merge_payload.get('replacements', []) or [],
                    'replace_rules': merge_payload.get('replace_rules', {}) or {},
                    'actions': int(merge_res.get('actions') or 0)
                }

        res['final_tags'] = final_tags
        if tag_merge:
            res['tag_merge'] = tag_merge

        logger.info(f"Auto-run forum tags on link update for {card_id}: {res}")
        return {"run": True, "result": res}

    except Exception as e:
        logger.error(f"Auto-run forum tags error: {e}")
        return None
