import logging

from core.utils.tag_parser import split_action_tags

logger = logging.getLogger(__name__)


def _normalize_tag_list(tags):
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',') if t and t.strip()]
    elif not isinstance(tags, (list, tuple, set)):
        return []

    out = []
    seen = set()
    for item in tags:
        tag = str(item).strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
    return out


def _parse_rule_entries(rule_data, slash_as_separator=False):
    parsed = {}

    if isinstance(rule_data, dict):
        items = rule_data.items()
    elif isinstance(rule_data, (list, tuple, set)):
        items = []
        for entry in rule_data:
            if isinstance(entry, str):
                items.append((entry, None))
    elif isinstance(rule_data, str):
        items = [(entry, None) for entry in split_action_tags(rule_data, slash_as_separator=slash_as_separator)]
    else:
        return parsed

    for raw_from, raw_to in items:
        from_tags = []
        to_tags = []

        if raw_to is None and isinstance(raw_from, str):
            text = raw_from.strip()
            splitter = None
            if '→' in text:
                splitter = '→'
            elif '->' in text:
                splitter = '->'
            elif '=>' in text:
                splitter = '=>'

            if not splitter:
                continue

            left, right = text.split(splitter, 1)
            from_tags = split_action_tags(left, slash_as_separator=slash_as_separator)
            to_tags = split_action_tags(right, slash_as_separator=slash_as_separator)
        else:
            from_tags = split_action_tags(raw_from, slash_as_separator=slash_as_separator)
            to_tags = split_action_tags(raw_to, slash_as_separator=slash_as_separator)

        if not from_tags or not to_tags:
            continue

        target = to_tags[0]
        for from_tag in from_tags:
            parsed[from_tag] = target

    return parsed


def parse_merge_rules(value, slash_as_separator=False):
    if not value:
        return {}

    if isinstance(value, dict):
        if 'replace_rules' in value:
            return _parse_rule_entries(value.get('replace_rules') or {}, slash_as_separator=slash_as_separator)

        if 'merge_rules' in value:
            return _parse_rule_entries(value.get('merge_rules') or {}, slash_as_separator=slash_as_separator)

        source_tags = value.get('source_tags') or value.get('from_tags')
        target_tag = value.get('target_tag') or value.get('target')
        if source_tags and target_tag:
            from_tags = split_action_tags(source_tags, slash_as_separator=slash_as_separator)
            return _parse_rule_entries(
                {'|'.join(from_tags): target_tag},
                slash_as_separator=slash_as_separator
            )

        reserved = {'exclude_tags', 'merge_mode'}
        if any(k in reserved for k in value.keys()):
            return {}

        return _parse_rule_entries(value, slash_as_separator=slash_as_separator)

    return _parse_rule_entries(value, slash_as_separator=slash_as_separator)


def _resolve_target(tag, replace_rules):
    current = tag
    seen = set()

    while current in replace_rules:
        if current in seen:
            logger.warning(f"Tag merge loop detected: {tag}")
            break
        seen.add(current)

        nxt = str(replace_rules.get(current) or '').strip()
        if not nxt:
            break
        current = nxt

    return current


def merge_tags_with_rules(tags, replace_rules):
    source_tags = _normalize_tag_list(tags)
    if not replace_rules:
        return {
            'tags': source_tags,
            'changed': False,
            'replacements': []
        }

    merged = []
    seen = set()
    replacements = []

    for tag in source_tags:
        target = _resolve_target(tag, replace_rules)
        if target != tag:
            replacements.append({'from': tag, 'to': target})

        if target and target not in seen:
            merged.append(target)
            seen.add(target)

    return {
        'tags': merged,
        'changed': merged != source_tags,
        'replacements': replacements
    }


def apply_merge_actions_to_tags(tags, actions, slash_as_separator=False):
    replace_rules = {}
    applied_actions = 0

    for action in (actions or []):
        if not isinstance(action, dict):
            continue

        parsed = parse_merge_rules(action.get('value'), slash_as_separator=slash_as_separator)
        if not parsed:
            continue

        replace_rules.update(parsed)
        applied_actions += 1

    merge_result = merge_tags_with_rules(tags, replace_rules)
    merge_result['replace_rules'] = replace_rules
    merge_result['actions'] = applied_actions
    return merge_result
