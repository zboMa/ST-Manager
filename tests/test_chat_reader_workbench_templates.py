from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def extract_css_block(css_source, selector):
    selector_start = css_source.index(selector)
    block_start = css_source.index('{', selector_start)
    block_end = css_source.index('}', block_start)
    return css_source[block_start + 1:block_end]


def extract_exact_css_block(css_source, selector):
    match = re.search(rf'(^|\n)\s*{re.escape(selector)}\s*\{{', css_source)
    if not match:
        raise ValueError(f'Exact selector not found: {selector}')

    selector_start = match.start()
    block_start = css_source.index('{', selector_start)
    block_end = css_source.index('}', block_start)
    return css_source[block_start + 1:block_end]


def extract_media_block(css_source, media_query):
    media_start = css_source.index(media_query)
    block_start = css_source.index('{', media_start)
    depth = 1
    index = block_start + 1

    while depth > 0:
        current_char = css_source[index]

        if current_char == '{':
            depth += 1
        elif current_char == '}':
            depth -= 1

        index += 1

    return css_source[block_start + 1:index - 1]


def extract_js_function_block(source, signature):
    function_start = source.index(signature)
    block_start = source.index('{', function_start)
    depth = 1
    index = block_start + 1

    while depth > 0:
        current_char = source[index]

        if current_char == '{':
            depth += 1
        elif current_char == '}':
            depth -= 1

        index += 1

    return source[block_start + 1:index - 1]


def extract_chat_reader_shell(template_source):
    shell_start = template_source.index('<div class="chat-reader-modal chat-reader-modal--fullscreen" role="dialog" aria-modal="true" aria-label="聊天阅读器">')
    settings_overlay_start = template_source.index('<div x-show="readerViewSettingsOpen"')
    return template_source[shell_start:settings_overlay_start]


def extract_balanced_tag_block(source, opening_tag):
    block_start = source.index(opening_tag)
    tag_name = opening_tag[1:opening_tag.index(' ')]
    opening_pattern = re.compile(rf'<{tag_name}(?:\s|>)')
    closing_tag = f'</{tag_name}>'
    depth = 0

    for match in opening_pattern.finditer(source, block_start):
        if match.start() == block_start:
            depth = 1
            index = match.end()
            break
    else:
        raise ValueError(f'Opening tag not found: {opening_tag}')

    while depth > 0:
        next_open = opening_pattern.search(source, index)
        next_close = source.find(closing_tag, index)

        if next_close == -1:
            raise ValueError(f'Closing tag not found for: {opening_tag}')

        if next_open and next_open.start() < next_close:
            depth += 1
            index = next_open.end()
            continue

        depth -= 1
        index = next_close + len(closing_tag)

    return source[block_start:index]


def extract_first_chat_message_card(template_source):
    floor_loop_start = template_source.index('<template x-for="message in visibleDetailMessages"')
    floor_markup = template_source[floor_loop_start:]
    return extract_balanced_tag_block(floor_markup, '<article class="chat-message-card"')


def test_header_template_does_not_expose_runtime_inspector_controls():
    header_template = read_project_file('templates/components/header.html')

    assert 'openRuntimeInspector' not in header_template
    assert 'open-runtime-inspector' not in header_template
    assert '运行时检查器' not in header_template
    assert 'title="运行时检查器"' not in header_template
    assert '<div class="menu-label">运行时</div>' not in header_template


def test_index_template_does_not_include_runtime_inspector_modal():
    index_template = read_project_file('templates/index.html')

    assert 'runtime_inspector.html' not in index_template
    assert 'runtime_inspector' not in index_template


def test_app_js_does_not_import_or_register_runtime_inspector():
    app_source = read_project_file('static/js/app.js')

    assert 'runtimeInspector' not in app_source
    assert 'runtimeInspector.js' not in app_source


def test_header_component_does_not_wire_runtime_inspector_events():
    header_source = read_project_file('static/js/components/header.js')

    assert 'openRuntimeInspector' not in header_source
    assert 'open-runtime-inspector' not in header_source


def test_advanced_editor_no_longer_listens_for_runtime_inspector_bridge_events():
    advanced_editor_source = read_project_file('static/js/components/advancedEditor.js')

    assert 'runtime-inspector-control' not in advanced_editor_source
    assert 'focus-script-runtime-owner' not in advanced_editor_source


def test_chat_reader_css_defines_workbench_theme_tokens():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    reader_overlay_block = extract_css_block(chat_reader_css, '.chat-reader-overlay')
    light_mode_overlay_block = extract_css_block(chat_reader_css, 'html.light-mode .chat-reader-overlay')

    required_tokens = [
        '--chat-reader-accent-soft',
        '--chat-reader-accent-strong',
        '--chat-reader-accent-border',
        '--chat-reader-accent-text',
        '--chat-reader-surface-raised',
        '--chat-reader-surface-selected',
        '--chat-reader-danger-soft',
        '--chat-reader-focus-ring',
    ]

    derived_token_prefixes = [
        '--chat-reader-accent-soft:',
        '--chat-reader-accent-strong:',
        '--chat-reader-accent-border:',
        '--chat-reader-accent-text:',
        '--chat-reader-surface-raised:',
        '--chat-reader-surface-selected:',
        '--chat-reader-focus-ring:',
    ]

    for token in required_tokens:
        assert token in chat_reader_css
        assert token in reader_overlay_block
        assert token in light_mode_overlay_block

    for block in (reader_overlay_block, light_mode_overlay_block):
        for line in block.splitlines():
            stripped_line = line.strip()

            if any(stripped_line.startswith(prefix) for prefix in derived_token_prefixes):
                assert '#' not in stripped_line


def test_chat_reader_icon_buttons_define_focus_visible_state():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')

    assert '.chat-reader-icon-button:focus-visible' in chat_reader_css
    assert 'outline: 2px solid var(--chat-reader-focus-ring)' in chat_reader_css
    assert 'outline-offset: 2px' in chat_reader_css


def test_chat_reader_css_caps_message_stream_width_with_reader_token():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    reader_overlay_block = extract_css_block(chat_reader_css, '.chat-reader-overlay')
    message_list_block = extract_exact_css_block(chat_reader_css, '.chat-message-list')

    assert '--chat-reader-reading-max-width:' in reader_overlay_block
    assert 'width: 100%;' in message_list_block
    assert 'max-width: var(--chat-reader-reading-max-width);' in message_list_block
    assert 'margin: 0 auto;' in message_list_block


def test_chat_reader_css_flattens_floor_cards_into_stream_sections():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    message_card_block = extract_exact_css_block(chat_reader_css, '.chat-message-card')
    message_card_before_block = extract_exact_css_block(chat_reader_css, '.chat-message-card::before')
    user_card_block = extract_exact_css_block(chat_reader_css, '.chat-message-card.is-user')
    assistant_card_block = extract_exact_css_block(chat_reader_css, '.chat-message-card.is-assistant')
    system_card_block = extract_exact_css_block(chat_reader_css, '.chat-message-card.is-system')

    assert 'border-radius: 0;' in message_card_block
    assert 'padding: 0;' in message_card_block
    assert 'background: transparent;' in message_card_block
    assert 'box-shadow: none;' in message_card_block
    assert 'content: none;' in message_card_before_block
    assert 'background: transparent;' in user_card_block
    assert 'background: transparent;' in assistant_card_block
    assert 'background: transparent;' in system_card_block
    assert '.chat-message-card + .chat-message-card {' in chat_reader_css


def test_chat_reader_css_light_mode_message_cards_do_not_restore_card_shadows():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')

    assert not re.search(
        r'html\.light-mode\s+[^\{]*\.chat-message-card[^\{]*\{[^\}]*box-shadow\s*:',
        chat_reader_css,
        re.DOTALL,
    )


def test_chat_reader_template_contains_workbench_regions():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')
    shell = extract_chat_reader_shell(reader_template)

    shell_pattern = re.compile(
        r'<div class="chat-reader-header" :class=".*?readerResponsiveMode.*?">.*?'
        r'<div class="chat-reader-body" :style="readerBodyGridStyle">.*?'
        r'<aside x-show="readerShowLeftPanel" class="chat-reader-left custom-scrollbar".*?>.*?'
        r'<main class="chat-reader-center custom-scrollbar" :style="readerCenterPaneStyle" @scroll.passive="handleReaderScroll\(\)">.*?'
        r'<aside x-show="readerShowRightPanel" class="chat-reader-right custom-scrollbar" :style="readerRightPaneStyle">',
        re.DOTALL,
    )

    assert shell_pattern.search(shell)
    assert shell.count('<aside ') == 2
    assert shell.index('class="chat-reader-header"') < shell.index('class="chat-reader-body"')
    assert '<div class="chat-reader-body" :style="readerBodyGridStyle">' in shell
    assert '<aside x-show="readerShowLeftPanel" class="chat-reader-left custom-scrollbar"' in shell
    assert '\n            </aside>\n\n            <main class="chat-reader-center custom-scrollbar" :style="readerCenterPaneStyle" @scroll.passive="handleReaderScroll()">' in shell
    assert '\n            </main>\n\n            <aside x-show="readerShowRightPanel" class="chat-reader-right custom-scrollbar" :style="readerRightPaneStyle">' in shell


def test_chat_reader_template_groups_desktop_workbench_controls():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'chat-reader-header-context' in reader_template
    assert 'chat-reader-header-primary' in reader_template
    assert 'chat-reader-header-secondary' in reader_template
    assert 'chat-reader-panel-group' in reader_template
    assert 'chat-reader-danger-zone' in reader_template
    assert 'chat-reader-icon-button' in reader_template


def test_chat_reader_template_includes_mobile_drawer_segments():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'readerMobilePanel' in reader_template
    assert "readerMobilePanel === 'tools'" in reader_template
    assert "readerMobilePanel === 'search'" in reader_template
    assert "readerMobilePanel === 'navigator'" in reader_template


def test_chat_grid_tracks_mobile_reader_panel_state():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert 'readerMobilePanel' in chat_grid_source


def test_chat_grid_reconciles_reader_panel_state_on_device_type_changes():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert 'reconcileReaderPanelsForDeviceType' in chat_grid_source
    assert "this.$watch('$store.global.deviceType'" in chat_grid_source
    assert 'this.reconcileReaderPanelsForDeviceType();' in chat_grid_source
    assert "if (responsiveMode === 'mobile')" in chat_grid_source
    assert "if (responsiveMode === 'tablet')" in chat_grid_source
    assert "this.readerMobilePanel = this.readerShowLeftPanel ? 'tools' : (this.readerRightTab === 'floors' ? 'navigator' : 'search');" in chat_grid_source
    assert "this.readerShowLeftPanel = this.readerMobilePanel === 'tools';" in chat_grid_source
    assert "this.readerShowRightPanel = true;" in chat_grid_source


def test_chat_reader_template_keeps_all_nested_modal_entry_points():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    for entry_point in (
        'readerViewSettingsOpen',
        'regexConfigOpen',
        'editingFloor',
        'bindPickerOpen',
    ):
        assert entry_point in reader_template


def test_chat_reader_template_exposes_reader_status_and_accessibility_hooks():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'role="dialog"' in reader_template
    assert 'aria-modal="true"' in reader_template
    assert 'aria-label="聊天阅读器"' in reader_template
    assert 'role="status"' in reader_template
    assert 'aria-live="polite"' in reader_template
    assert 'role="alert"' in reader_template
    assert 'aria-live="assertive"' in reader_template
    assert 'aria-label="关闭工具栏"' in reader_template
    assert ':aria-label="readerMobilePanelCloseLabel"' in reader_template
    assert 'aria-label="关闭聊天阅读器"' in reader_template
    assert ":aria-label=\"isBookmarked(message.floor) ? '取消收藏楼层' : '收藏楼层'\"" in reader_template
    assert '危险操作 · 删除会直接移除当前聊天记录' in reader_template
    assert 'role="note"' in reader_template
    assert 'readerShellStatusText' in reader_template
    assert 'readerSaveFeedbackTone' in reader_template
    assert "readerMobilePanelCloseLabel" in reader_template
    assert ':aria-label="readerMobilePanelCloseLabel"' in reader_template
    assert ':title="readerMobilePanelCloseLabel"' in reader_template
    assert '@keydown.escape.window.prevent="readerViewSettingsOpen = false"' in reader_template
    assert '@keydown.escape.window.prevent="closeRegexConfig()"' in reader_template
    assert '@keydown.escape.window.prevent="closeFloorEditor()"' in reader_template
    assert '@keydown.escape.window.prevent="closeBindPicker()"' in reader_template


def test_chat_grid_resets_reader_feedback_tone_to_steady_state():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert 'setReaderFeedbackTone(tone = \'neutral\')' in chat_grid_source
    assert "if (tone === 'error' || tone === 'danger' || tone === 'success')" in chat_grid_source
    assert "this.readerSaveFeedbackTone = this.replaceStatus || this.regexConfigStatus ? 'neutral' : 'neutral';" not in chat_grid_source
    assert "this.readerSaveFeedbackTone = this.replaceStatus || this.regexConfigStatus ? 'neutral' : 'neutral'" not in chat_grid_source
    assert 'this.setReaderFeedbackTone();' in chat_grid_source


def test_chat_reader_css_defines_distinct_tablet_and_mobile_breakpoints():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')

    assert '@media (max-width: 1179px)' in chat_reader_css
    assert '@media (max-width: 899px)' in chat_reader_css


def test_chat_reader_template_keeps_header_identity_and_action_groups():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'chat-reader-header-main' in reader_template
    assert 'chat-reader-header-context' in reader_template
    assert 'chat-reader-header-actions' in reader_template
    assert 'chat-reader-header-tools' in reader_template
    assert 'chat-reader-shell-status-text' in reader_template


def test_chat_reader_css_promotes_shell_status_to_second_header_row():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')

    header_block = extract_exact_css_block(chat_reader_css, '.chat-reader-header')
    main_block = extract_exact_css_block(chat_reader_css, '.chat-reader-header-main')
    actions_block = extract_exact_css_block(chat_reader_css, '.chat-reader-header-actions')
    shell_status_block = extract_exact_css_block(chat_reader_css, '.chat-reader-shell-status')

    assert 'flex-wrap: wrap' in header_block
    assert 'align-items: stretch' in header_block
    assert 'flex: 1 1 34rem' in main_block
    assert 'min-width: min(100%, 24rem)' in main_block
    assert 'max-width: 100%' in actions_block
    assert 'flex: 1 0 100%' in shell_status_block
    assert 'margin-top: 0' in shell_status_block


def test_chat_reader_css_keeps_tablet_actions_in_single_wrapping_row():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    tablet_block = extract_media_block(chat_reader_css, '@media (max-width: 1179px)')

    tablet_actions_block = extract_exact_css_block(tablet_block, '.chat-reader-header-actions')
    tablet_primary_block = extract_exact_css_block(tablet_block, '.chat-reader-header-primary')
    tablet_tools_block = extract_exact_css_block(tablet_block, '.chat-reader-header-tools')

    assert 'justify-content: flex-start' in tablet_actions_block
    assert 'align-items: center' in tablet_actions_block
    assert 'flex-direction: row' in tablet_primary_block
    assert 'align-items: center' in tablet_primary_block
    assert 'justify-content: flex-start' in tablet_tools_block


def test_chat_reader_css_rebalances_header_rows_at_narrow_widths():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    tablet_block = extract_media_block(chat_reader_css, '@media (max-width: 1179px)')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    assert '.chat-reader-header-main,\n    .chat-reader-header-actions,\n    .chat-reader-header-context,\n    .chat-reader-header-primary,\n    .chat-reader-header-tools,\n    .chat-reader-header-stats {' not in tablet_block

    header_block = extract_css_block(tablet_block, '.chat-reader-header')
    assert 'flex-wrap: wrap' in header_block
    assert 'align-items: stretch' in header_block
    assert '.chat-grid-toolbar-actions,\n    .chat-reader-header,\n    .chat-reader-header-main {' not in tablet_block

    assert '.chat-reader-title-wrap {' in tablet_block
    assert 'width: 100%' in extract_css_block(tablet_block, '.chat-reader-title-wrap')

    title_block = extract_css_block(tablet_block, '.chat-reader-title')
    assert 'overflow-wrap: break-word' in title_block
    assert 'word-break: keep-all' in title_block

    assert '.chat-reader-header-actions {' in tablet_block
    tablet_actions_block = extract_css_block(tablet_block, '.chat-reader-header-actions')
    assert 'width: 100%;' in tablet_actions_block
    assert 'flex-wrap: wrap;' in tablet_actions_block

    assert '.chat-reader-shell-status {' in tablet_block
    tablet_status_block = extract_css_block(tablet_block, '.chat-reader-shell-status')
    assert 'display: flex;' in tablet_status_block
    assert 'width: 100%;' in tablet_status_block
    assert 'flex-basis: 100%;' in tablet_status_block
    assert 'margin-top: 0;' in tablet_status_block

    assert '.chat-reader-header-main,' in mobile_block
    assert '.chat-reader-header-actions,' in mobile_block
    assert '.chat-reader-header-primary {' in mobile_block
    assert 'width: 100%;' in mobile_block
    assert '.chat-reader-header-tools {' in mobile_block
    mobile_tools_block = extract_css_block(mobile_block, '.chat-reader-header-tools')
    assert 'flex-direction: row;' in mobile_tools_block
    assert 'justify-content: flex-start' in mobile_tools_block


def test_chat_grid_mobile_reader_panel_state_keeps_one_active_panel():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert "this.readerShowLeftPanel = active === 'tools';" in chat_grid_source
    assert "this.readerShowRightPanel = active === 'search' || active === 'navigator';" in chat_grid_source
    assert 'this.readerShowRightPanel = Boolean(active);' not in chat_grid_source


def test_chat_grid_reader_responsive_mode_uses_reactive_device_type_instead_of_window_width():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert "const deviceType = this.$store.global.deviceType;" in chat_grid_source
    assert "if (deviceType === 'mobile')" in chat_grid_source
    assert "if (deviceType === 'tablet')" in chat_grid_source
    assert 'window.innerWidth < 900' not in chat_grid_source
    assert 'window.innerWidth < 1180' not in chat_grid_source


def test_chat_grid_reader_body_grid_style_drives_desktop_tablet_and_mobile_layouts_from_panel_state():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert "return 'grid-template-columns: minmax(0, 1fr);';" in chat_grid_source
    assert "return `grid-template-columns: ${leftWidth}px minmax(0, 1fr);`;" in chat_grid_source
    assert "return `grid-template-columns: minmax(0, 1fr) ${rightWidth}px;`;" in chat_grid_source
    assert "return `grid-template-columns: ${leftWidth}px minmax(0, 1fr) ${rightWidth}px;`;" in chat_grid_source


def test_chat_reader_template_assigns_dynamic_grid_columns_to_center_and_right_panes():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert ":style=\"readerCenterPaneStyle\"" in reader_template
    assert ":style=\"readerRightPaneStyle\"" in reader_template
    assert ":style=\"readerLeftPaneStyle\"" in reader_template


def test_chat_reader_template_keeps_floor_anchor_article_and_actions():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')
    floor_markup = extract_first_chat_message_card(reader_template)
    header_block = extract_balanced_tag_block(floor_markup, '<div class="chat-message-head">')

    assert '<article class="chat-message-card"' in floor_markup
    assert ':data-chat-floor="message.floor"' in floor_markup

    for action_hook in (
        '@click="scrollToFloor(message.floor)"',
        '@click="toggleBookmark(message)"',
        '@click="openMessageAsAppStage(message)"',
        '@click="openFloorEditor(message)"',
    ):
        assert action_hook in header_block


def test_chat_reader_template_wraps_floor_content_in_message_body():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert '<div class="chat-message-body">' in reader_template


def test_chat_reader_template_keeps_header_actions_ahead_of_message_body():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')
    floor_markup = extract_first_chat_message_card(reader_template)

    assert floor_markup.index('class="chat-message-head"') < floor_markup.index('class="chat-message-body"')


def test_chat_reader_template_places_timebar_inside_message_body():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')
    floor_markup = extract_first_chat_message_card(reader_template)
    body_block = extract_balanced_tag_block(floor_markup, '<div class="chat-message-body">')

    assert 'class="chat-message-timebar"' in body_block


def test_chat_reader_css_keeps_floor_chip_as_primary_reader_anchor():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')

    floor_chip_block = extract_exact_css_block(chat_reader_css, '.chat-floor-chip')

    assert 'padding: 0.34rem 0.62rem;' in floor_chip_block
    assert 'font-weight: 700;' in floor_chip_block


def test_chat_reader_css_softens_bookmark_button_and_secondary_floor_actions():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')

    bookmark_toggle_block = extract_exact_css_block(chat_reader_css, '.chat-bookmark-toggle')
    secondary_floor_chip_block = extract_exact_css_block(
        chat_reader_css,
        '.chat-message-floor-wrap .chat-floor-chip:not(:first-child)',
    )
    light_mode_secondary_floor_chip_block = extract_exact_css_block(
        chat_reader_css,
        'html.light-mode .chat-message-floor-wrap .chat-floor-chip:not(:first-child)',
    )

    assert 'background: transparent;' in bookmark_toggle_block
    assert 'border-color: transparent;' in bookmark_toggle_block
    assert 'color: var(--text-dim);' in bookmark_toggle_block

    assert 'padding: 0.28rem 0.52rem;' in secondary_floor_chip_block
    assert 'font-weight: 600;' in secondary_floor_chip_block
    assert 'color: color-mix(in srgb, var(--text-dim), var(--text-main) 22%);' in secondary_floor_chip_block

    assert 'color: #475569;' in light_mode_secondary_floor_chip_block


def test_chat_reader_css_mobile_drawer_starts_below_header_instead_of_centering_content():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    assert 'padding: calc(var(--chat-reader-header-height) + 0.55rem) 0.85rem 1rem;' not in mobile_block
    assert 'top: var(--chat-reader-header-height);' in mobile_block
    assert 'padding: 0.85rem 0.85rem 1rem;' in mobile_block


def test_chat_reader_template_moves_mobile_meta_out_of_the_header_shell():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'readerShellStatusLineText' in reader_template
    assert 'x-show="readerResponsiveMode === \'mobile\'"' in reader_template
    assert '聊天概览' in reader_template


def test_chat_reader_css_compacts_mobile_header_for_reading_first_layout():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    assert '.chat-reader-header {' in mobile_block
    assert 'padding: 0.62rem 0.72rem;' in mobile_block
    assert '.chat-reader-header-main {' in mobile_block
    assert 'flex: 1 1 auto;' in mobile_block
    assert '.chat-reader-header-actions {' in mobile_block
    assert 'align-items: center;' in mobile_block
    assert '.chat-reader-header-tools {' in mobile_block
    assert 'flex-direction: row;' in mobile_block
    assert '.chat-reader-header-secondary {' in mobile_block
    assert 'position: absolute;' in mobile_block


def test_chat_reader_css_mobile_toggle_buttons_use_compact_chip_widths():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    assert '.chat-reader-toggle {' in mobile_block
    assert 'width: auto;' in mobile_block
    assert 'min-width: 0;' in mobile_block
    assert '.chat-toolbar-btn--primary.chat-reader-mobile-save {' in mobile_block


def test_chat_reader_template_removes_duplicate_top_stats_and_keeps_single_status_row():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'chat-reader-header-stats' not in reader_template
    assert 'x-text="readerShellStatusLineText"' in reader_template
    assert 'chat-reader-state-pill' not in reader_template
    assert 'x-text="readerViewportStatusText"' not in reader_template.split('chat-reader-header', 1)[1].split('chat-reader-body', 1)[0]
    assert 'x-text="readerAnchorStatusText"' not in reader_template.split('chat-reader-header', 1)[1].split('chat-reader-body', 1)[0]


def test_chat_grid_exposes_status_line_text_with_message_count_and_anchor_summary():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert 'get readerShellStatusLineText() {' in chat_grid_source
    assert 'activeChat?.message_count' in chat_grid_source
    assert 'readerAnchorStatusText' in chat_grid_source


def test_chat_reader_template_exposes_semi_auto_anchor_mode_in_both_anchor_control_groups():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')
    anchor_mode_groups = re.findall(
        r'<div class="chat-reader-option-group-label">锚点模式</div>\s*<div class="chat-inline-actions">(.*?)</div>',
        reader_template,
        re.DOTALL,
    )

    assert len(anchor_mode_groups) >= 2
    assert sum('半自动迁移' in group for group in anchor_mode_groups) >= 2
    assert sum("@click=\"setReaderAnchorMode('semi_auto')\"" in group for group in anchor_mode_groups) >= 2


def test_chat_reader_template_reasoningDefaultCollapsed_view_strategy_control_matches_approved_label():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')
    settings_modal = extract_balanced_tag_block(
        reader_template,
        '<div x-show="readerViewSettingsOpen"',
    )

    assert re.search(
        r'<label class="chat-reader-field">\s*<span>Reasoning 默认折叠</span>\s*<label class="chat-inline-checkbox">.*?<input type="checkbox" x-model="readerViewSettings\.reasoningDefaultCollapsed">',
        settings_modal,
        re.DOTALL,
    )


def test_chat_reader_template_autoCollapseLongCode_view_strategy_control_uses_settings_modal_checkbox_structure():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')
    settings_modal = extract_balanced_tag_block(
        reader_template,
        '<div x-show="readerViewSettingsOpen"',
    )

    assert re.search(
        r'<label class="chat-reader-field">\s*<span>长代码自动折叠</span>\s*<label class="chat-inline-checkbox">.*?<input type="checkbox" x-model="readerViewSettings\.autoCollapseLongCode">',
        settings_modal,
        re.DOTALL,
    )


def test_chat_reader_css_exposes_reasoning_and_code_collapse_primitives():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')

    for selector in (
        '.chat-message-reasoning',
        '.chat-message-reasoning-summary',
        '.chat-message-code-collapse',
        '.chat-message-meta-flags',
    ):
        assert selector in chat_reader_css


def test_chat_reader_css_positions_mobile_close_button_in_header_corner():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    assert '.chat-reader-header {' in mobile_block
    assert 'position: sticky;' in mobile_block or 'position: sticky' in mobile_block
    assert '.chat-reader-header-secondary {' in mobile_block
    assert 'position: absolute;' in mobile_block
    assert 'top: 0.62rem;' in mobile_block
    assert 'right: 0.72rem;' in mobile_block


def test_chat_grid_mobile_reader_toggles_can_close_same_panel_on_repeat_tap():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    toggle_block = extract_js_function_block(chat_grid_source, 'toggleReaderPanel(side) {')
    set_mobile_block = extract_js_function_block(chat_grid_source, 'setReaderMobilePanel(panel) {')

    assert "const isSamePanelOpen = this.readerMobilePanel === panel;" in toggle_block
    assert "&& this.readerShowRightPanel" not in toggle_block
    assert "if (this.readerMobilePanel === normalized) {" in set_mobile_block
    assert 'this.hideReaderPanels();' in set_mobile_block


def test_chat_grid_scroll_to_floor_closes_mobile_drawers_before_showing_target_floor():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')
    scroll_block = extract_js_function_block(chat_grid_source, "async scrollToFloor(floor, persist = true, behavior = 'smooth', anchorSource = READER_ANCHOR_SOURCES.JUMP) {")

    assert "const shouldHideMobilePanel = this.readerResponsiveMode === 'mobile' && Boolean(this.readerMobilePanel);" in scroll_block
    assert 'if (shouldHideMobilePanel) {' in scroll_block
    assert 'this.hideReaderPanels();' in scroll_block


def test_chat_reader_css_enables_touch_scrolling_in_mobile_reading_column():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')

    assert '.chat-reader-center {' in chat_reader_css
    assert 'touch-action: pan-y;' in chat_reader_css
    assert '-webkit-overflow-scrolling: touch;' in chat_reader_css
    assert 'overscroll-behavior-y: contain;' in chat_reader_css


def test_chat_reader_css_uses_theme_surface_backgrounds_for_mobile_drawers():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    assert 'background: var(--bg-panel);' in mobile_block
    assert 'border-top: 1px solid var(--border-main);' in mobile_block
    assert 'backdrop-filter: blur(16px);' not in mobile_block
    assert '-webkit-backdrop-filter: blur(16px);' not in mobile_block


def test_chat_grid_scroll_element_to_top_uses_container_rect_delta_instead_of_offset_top_math():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')
    scroll_block = extract_js_function_block(chat_grid_source, "scrollElementToTop(el, behavior = 'smooth') {")

    assert 'const containerRect = container.getBoundingClientRect();' in scroll_block
    assert 'const elementRect = el.getBoundingClientRect();' in scroll_block
    assert 'const top = Math.max(0, container.scrollTop + elementRect.top - containerRect.top - 12);' in scroll_block
    assert 'el.offsetTop - container.offsetTop - 12' not in scroll_block


def test_chat_reader_css_mobile_shell_keeps_main_reader_area_as_scroll_container():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    assert '.chat-reader-modal {' in mobile_block
    assert 'height: 100dvh;' in mobile_block
    assert '.chat-reader-body {' in mobile_block
    assert 'flex: 1 1 auto;' in mobile_block
    assert 'min-height: 0;' in mobile_block
    assert '.chat-reader-center {' in mobile_block
    assert 'overflow-y: auto;' in mobile_block
    assert '-webkit-overflow-scrolling: touch;' in mobile_block


def test_chat_reader_css_mobile_stream_uses_tight_safe_gutters():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    center_block = extract_exact_css_block(mobile_block, '.chat-reader-center')
    list_block = extract_exact_css_block(mobile_block, '.chat-message-list')
    card_spacing_block = extract_exact_css_block(mobile_block, '.chat-message-card + .chat-message-card')

    assert 'padding: 0.55rem 0.45rem 1rem;' in center_block
    assert 'max-width: none;' in list_block
    assert 'margin-top: 1.1rem;' in card_spacing_block
    assert 'padding-top: 1rem;' in card_spacing_block


def test_chat_reader_css_mobile_floor_header_wraps_actions_and_meta():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    head_block = extract_exact_css_block(mobile_block, '.chat-message-head')
    floor_wrap_block = extract_exact_css_block(mobile_block, '.chat-message-floor-wrap')
    meta_block = extract_exact_css_block(mobile_block, '.chat-message-meta')

    assert 'flex-wrap: wrap;' in head_block
    assert 'flex-wrap: wrap;' in floor_wrap_block
    assert 'width: 100%;' in meta_block
    assert 'align-items: flex-start;' in meta_block
    assert 'text-align: left;' in meta_block


def test_chat_reader_css_tablet_stream_keeps_moderate_reading_cap():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    tablet_block = extract_media_block(chat_reader_css, '@media (max-width: 1179px)')

    list_block = extract_exact_css_block(tablet_block, '.chat-message-list')

    assert 'max-width: 64rem;' in list_block


def test_chat_reader_css_mobile_nested_modals_expose_internal_scroll_regions():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 720px)')

    assert '.chat-reader-nested-modal,' in mobile_block
    assert 'display: flex;' in mobile_block
    assert 'flex-direction: column;' in mobile_block
    assert 'overflow: hidden;' in mobile_block
    assert '.chat-reader-editor-grid,' in mobile_block
    assert 'overflow-y: auto;' in mobile_block
    assert '.chat-reader-regex-help-body,' in mobile_block
    assert '.chat-reader-floor-preview {' in mobile_block


def test_layout_css_adds_light_mode_mobile_header_and_footer_surfaces():
    layout_css = read_project_file('static/css/modules/layout.css')

    assert 'html.light-mode .header-bar,' in layout_css
    assert 'html.light-mode .pagination-bar {' in layout_css


def test_header_listens_for_global_mobile_menu_close_requests():
    header_source = read_project_file('static/js/components/header.js')

    assert "window.addEventListener('close-header-mobile-menu'" in header_source
    assert 'this.closeMobileMenu();' in header_source


def test_chat_grid_closes_mobile_navigation_chrome_before_showing_reader():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')
    open_detail_block = extract_js_function_block(chat_grid_source, 'async openChatDetail(item) {')

    assert "if (this.$store.global.deviceType === 'mobile') {" in open_detail_block
    assert 'this.$store.global.visibleSidebar = false;' in open_detail_block
    assert "document.body.style.overflow = '';" in open_detail_block
    assert "window.dispatchEvent(new CustomEvent('close-header-mobile-menu'));" in open_detail_block


def test_chat_grid_closes_mobile_navigation_chrome_before_opening_reader_nested_modals():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    for signature in ('openRegexConfig() {', 'openRegexHelp() {', 'openFloorEditor(message) {'):
        block = extract_js_function_block(chat_grid_source, signature)
        assert "if (this.$store.global.deviceType === 'mobile') {" in block
        assert 'this.$store.global.visibleSidebar = false;' in block
        assert "document.body.style.overflow = '';" in block
        assert "window.dispatchEvent(new CustomEvent('close-header-mobile-menu'));" in block


def test_chat_grid_temporarily_releases_document_scroll_lock_while_reader_is_open():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    helper_block = extract_js_function_block(chat_grid_source, 'setMobileReaderDocumentScrollState(enabled = false) {')
    open_detail_block = extract_js_function_block(chat_grid_source, 'async openChatDetail(item) {')
    close_detail_block = extract_js_function_block(chat_grid_source, 'closeChatDetail() {')

    assert "document.documentElement.style.overflow = enabled ? 'auto' : '';" in helper_block
    assert "document.body.style.overflow = enabled ? 'auto' : '';" in helper_block
    assert "document.body.style.height = enabled ? 'auto' : '';" in helper_block
    assert 'this.setMobileReaderDocumentScrollState(true);' in open_detail_block
    assert 'this.setMobileReaderDocumentScrollState(false);' in close_detail_block


def test_chat_reader_css_marks_mobile_scroll_regions_as_touch_pan_targets():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')

    assert '.chat-reader-modal,' in chat_reader_css
    assert '.chat-reader-regex-help-body,' in chat_reader_css
    assert '.chat-reader-editor-grid,' in chat_reader_css
    assert '.chat-reader-floor-preview,' in chat_reader_css
    assert '.chat-bind-results {' in chat_reader_css
    assert 'touch-action: pan-y;' in chat_reader_css


def test_chat_grid_collapses_mobile_header_layout_height_when_header_is_hidden():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')
    metrics_block = extract_js_function_block(chat_grid_source, 'updateReaderLayoutMetrics() {')

    assert "const effectiveHeaderHeight = this.readerResponsiveMode === 'mobile' && this.readerMobileHeaderHidden" in metrics_block
    assert "? 0" in metrics_block
    assert "root.style.setProperty('--chat-reader-header-height', `${effectiveHeaderHeight}px`);" in metrics_block


def test_chat_reader_css_mobile_hidden_header_releases_layout_space():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    assert '.chat-reader-header.is-mobile-hidden {' in mobile_block
    assert 'min-height: 0;' in mobile_block
    assert 'max-height: 0;' in mobile_block
    assert 'padding-top: 0;' in mobile_block
    assert 'padding-bottom: 0;' in mobile_block
    assert 'border-bottom-width: 0;' in mobile_block
    assert 'margin-bottom: 0;' in mobile_block


def test_chat_reader_css_mobile_header_defines_transition_for_smoother_hide_and_show():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    header_block = extract_exact_css_block(chat_reader_css, '.chat-reader-header')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 899px)')

    assert 'transition:' in header_block
    assert 'transform 0.24s cubic-bezier(0.22, 1, 0.36, 1)' in header_block
    assert 'opacity 0.18s ease' in header_block
    assert 'max-height 0.24s cubic-bezier(0.22, 1, 0.36, 1)' in header_block
    assert 'padding 0.24s cubic-bezier(0.22, 1, 0.36, 1)' in header_block
    assert 'border-color 0.18s ease' in header_block
    assert 'will-change: transform, opacity, max-height;' in header_block
    assert 'transform: translateY(calc(-100% - 0.35rem)) scaleY(0.98);' in mobile_block
    assert 'transform-origin: top center;' in mobile_block


def test_chat_grid_updates_layout_metrics_when_mobile_header_visibility_flips():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')
    helper_block = extract_js_function_block(chat_grid_source, 'syncReaderMobileHeaderVisibility(container) {')
    scroll_block = extract_js_function_block(chat_grid_source, 'handleReaderScroll() {')

    assert 'const previousHidden = this.readerMobileHeaderHidden;' in helper_block
    assert 'if (previousHidden !== this.readerMobileHeaderHidden) {' in helper_block
    assert 'this.updateReaderLayoutMetrics();' in helper_block
    assert 'this.syncReaderMobileHeaderVisibility(center);' in scroll_block


def test_chat_grid_extracts_mobile_header_scroll_logic_for_scroll_and_page_modes():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')
    helper_block = extract_js_function_block(chat_grid_source, 'syncReaderMobileHeaderVisibility(container) {')
    scroll_block = extract_js_function_block(chat_grid_source, 'handleReaderScroll() {')

    assert 'const nextTop = Math.max(0, Number(container.scrollTop || 0));' in helper_block
    assert 'const delta = nextTop - Number(this.readerLastScrollTop || 0);' in helper_block
    assert 'if (nextTop <= 24 || delta < -14) {' in helper_block
    assert '} else if (delta > 18 && nextTop > 72) {' in helper_block
    assert 'this.readerLastScrollTop = nextTop;' in helper_block
    assert 'this.syncReaderMobileHeaderVisibility(center);' in scroll_block
    assert scroll_block.index('this.syncReaderMobileHeaderVisibility(center);') < scroll_block.index('if (this.isReaderPageMode) {')


def test_chat_grid_scroll_reader_center_to_top_reveals_mobile_header_before_resetting_scroll():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')
    scroll_top_block = extract_js_function_block(chat_grid_source, "scrollReaderCenterToTop(behavior = 'auto') {")

    assert 'const previousHidden = this.readerMobileHeaderHidden;' in scroll_top_block
    assert 'this.readerMobileHeaderHidden = false;' in scroll_top_block
    assert 'this.readerLastScrollTop = 0;' in scroll_top_block
    assert 'if (previousHidden) {' in scroll_top_block
    assert 'this.updateReaderLayoutMetrics();' in scroll_top_block
    assert 'center.scrollTo({' in scroll_top_block


def test_chat_reader_template_moves_save_button_into_local_notes_panels():
    template_source = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'chat-reader-mobile-save' not in template_source
    assert 'x-show="readerResponsiveMode !== \'mobile\'" @click="saveChatMeta()">保存备注</button>' not in template_source
    assert template_source.count('@click="saveChatMeta()"') >= 2
    assert 'chat-reader-field-actions' in template_source


def test_chat_reader_template_keeps_modal_close_actions_separate_from_regex_toolbar_groups():
    template_source = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'chat-reader-modal-close-slot' in template_source
    assert '<div class="chat-reader-regex-toolbar chat-reader-nested-actions">' in template_source
    assert '<div class="chat-reader-regex-toolbar-group">' in template_source


def test_chat_reader_css_mobile_modal_headers_pin_close_buttons_to_right():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 720px)')

    assert '.chat-reader-nested-header,' in mobile_block
    assert 'display: grid;' in mobile_block
    assert 'grid-template-columns: minmax(0, 1fr) auto;' in mobile_block
    assert '.chat-reader-modal-close-slot {' in mobile_block
    assert 'justify-self: end;' in mobile_block
    assert 'align-self: start;' in mobile_block


def test_chat_reader_css_mobile_keeps_floor_editor_inputs_and_preview_min_height():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 720px)')

    assert '.chat-reader-floor-editor {' in mobile_block
    assert 'min-height: 11rem;' in mobile_block
    assert '.chat-reader-floor-preview {' in mobile_block
    assert 'min-height: 11rem;' in mobile_block


def test_chat_reader_template_groups_reader_controls_into_clear_sections():
    template_source = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'chat-reader-option-group-label">显示模式<' in template_source
    assert 'chat-reader-option-group-label">浏览方式<' in template_source
    assert 'chat-reader-option-group-label">规则与策略<' in template_source
    assert 'chat-reader-option-group-label">锚点模式<' in template_source
    assert 'chat-reader-option-group-label">快捷跳转<' in template_source
    assert 'chat-reader-option-group' in template_source


def test_chat_reader_css_mobile_allows_view_strategy_and_regex_summary_to_scroll():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 720px)')

    assert '.chat-reader-regex-summary-strip {' in mobile_block
    assert 'max-height: none;' in mobile_block
    assert '.chat-reader-nested-section--form {' in mobile_block
    assert 'overflow-y: auto;' in mobile_block


def test_chat_reader_template_floor_editor_uses_section_heads_and_editor_note():
    template_source = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'chat-reader-section-head' in template_source
    assert 'chat-reader-editor-note' in template_source


def test_chat_reader_css_mobile_regex_summary_becomes_inline_and_browser_keeps_space():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 720px)')

    assert '.chat-reader-regex-summary-strip--mobile {' in mobile_block
    assert 'padding-right: 0;' in mobile_block
    assert '.chat-reader-regex-summary-grid {' in mobile_block
    assert 'grid-template-columns: repeat(2, minmax(0, 1fr));' in mobile_block
    assert '.chat-reader-regex-summary-chip {' in mobile_block
    assert 'padding: 0.55rem 0.65rem;' in mobile_block
    assert '.chat-reader-regex-browser {' in mobile_block
    assert 'min-height: 18rem;' in mobile_block
    assert '.chat-reader-sideblock-card--browser {' in mobile_block
    assert 'min-height: 14rem;' in mobile_block
    assert '.chat-reader-sideblock-card--test {' in mobile_block
    assert 'min-height: 16rem;' in mobile_block
    assert 'max-height: 20rem;' in mobile_block
    assert '.chat-reader-regex-workbench {' in mobile_block
    assert 'gap: 0.8rem;' in mobile_block
    assert '.chat-reader-regex-browser-detail {' in mobile_block
    assert 'max-height: 16rem;' in mobile_block
    assert '.chat-reader-regex-test-input {' in mobile_block
    assert 'min-height: 8rem;' in mobile_block
    assert '.chat-reader-regex-preview {' in mobile_block
    assert 'min-height: 10rem;' in mobile_block
    assert '.chat-reader-editor-grid--balanced {' in mobile_block
    assert 'display: flex;' in mobile_block
    assert 'flex-direction: column;' in mobile_block
    assert '.chat-reader-regex-mobile-layout {' in mobile_block
    assert 'display: flex;' in mobile_block
    assert 'overflow-y: auto;' in mobile_block
    assert '.chat-reader-regex-mobile-tabs {' in mobile_block
    assert 'display: flex;' in mobile_block
    assert 'position: sticky;' in mobile_block
    assert '.chat-reader-regex-toolbar {' in mobile_block
    assert 'display: none;' in mobile_block
    assert '.chat-reader-regex-mobile-section {' in mobile_block
    assert 'display: flex;' in mobile_block
    assert 'flex-direction: column;' in mobile_block
    assert '.chat-reader-regex-mobile-layout .chat-reader-regex-browser {' in mobile_block
    assert 'grid-template-columns: 1fr;' in mobile_block
    assert '.chat-reader-regex-mobile-layout .chat-reader-regex-browser-list,' in mobile_block
    assert 'overflow: visible;' in mobile_block
    assert 'max-height: none;' in mobile_block
    assert '.chat-reader-regex-header-actions {' in mobile_block
    assert 'display: flex;' in mobile_block
    assert '.chat-reader-editor-grid--balanced {' in mobile_block
    assert 'display: none;' in mobile_block
    assert '.chat-reader-editor-grid--editor {' in mobile_block
    assert 'display: flex !important;' in mobile_block


def test_chat_reader_template_renders_regex_summary_inside_scrollable_mobile_workspace():
    template_source = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'class="chat-reader-regex-summary-strip chat-reader-nested-section chat-reader-nested-section--summary custom-scrollbar" x-show="readerResponsiveMode !== \'mobile\'"' in template_source
    assert 'chat-reader-regex-summary-strip--mobile' in template_source
    assert '<div class="chat-reader-regex-mobile-layout custom-scrollbar" x-show="readerResponsiveMode === \'mobile\'" @scroll.passive="handleRegexConfigScroll($event)">' in template_source


def test_chat_reader_template_adds_mobile_only_regex_sections_for_effective_rules_draft_and_test():
    template_source = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'chat-reader-regex-mobile-layout' in template_source
    assert 'chat-reader-regex-mobile-tabs' in template_source
    assert 'chat-reader-regex-mobile-section--effective' in template_source
    assert 'chat-reader-regex-mobile-section--draft' in template_source
    assert 'chat-reader-regex-mobile-section--test' in template_source
    assert "@click=\"regexConfigMobileTab = 'effective'\"" in template_source
    assert "@click=\"regexConfigMobileTab = 'draft'\"" in template_source
    assert "x-show=\"regexConfigMobileTab === 'effective'\"" in template_source
    assert "x-show=\"regexConfigMobileTab === 'draft'\"" in template_source
    assert 'chat-reader-regex-mobile-savebar' not in template_source
    assert 'chat-reader-regex-header-actions' in template_source
    assert "x-show=\"readerResponsiveMode === 'mobile'\" class=\"chat-toolbar-btn chat-toolbar-btn--primary chat-reader-regex-save-pill\" @click=\"saveRegexConfig()\">保存</button>" in template_source


def test_chat_grid_tracks_mobile_regex_header_visibility_separately_from_reader_header():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert 'regexConfigMobileHeaderHidden: false,' in chat_grid_source
    assert "regexConfigMobileTab: 'effective'," in chat_grid_source
    regex_scroll_block = extract_js_function_block(chat_grid_source, 'handleRegexConfigScroll(event) {')
    assert 'const previousHidden = this.regexConfigMobileHeaderHidden;' in regex_scroll_block
    assert 'this.regexConfigMobileHeaderHidden = true;' in regex_scroll_block
    assert 'this.updateRegexConfigLayoutMetrics();' in regex_scroll_block


def test_chat_reader_template_mobile_floor_editor_keeps_right_column_note_inside_section_head():
    template_source = read_project_file('templates/modals/detail_chat_reader.html')
    editor_block = template_source.split('<div class="chat-reader-editor-section chat-reader-editor-section--wide chat-reader-nested-section">', 1)[1].split('<div class="chat-inline-actions">', 1)[0]

    assert '<div class="chat-reader-section-head">' in editor_block
    assert '<div class="chat-reader-panel-title">显示预览</div>' in editor_block
    assert 'chat-reader-editor-note' in editor_block


def test_chat_reader_template_uses_raw_message_as_floor_editor_primary_input():
    template_source = read_project_file('templates/modals/detail_chat_reader.html')
    floor_editor_block = template_source.split('<div class="chat-bind-modal chat-reader-editor-modal chat-reader-nested-modal chat-reader-transition-surface chat-reader-editor-modal--floor"', 1)[1].split('</div>\n</div>\n\n<div x-show="bindPickerOpen"', 1)[0]

    assert '<div class="chat-reader-panel-title">原始正文</div>' in floor_editor_block
    assert '<textarea x-model="editingMessageRawDraft" @input="editingMessageDraft = extractDisplayContent($event.target.value)" class="form-textarea chat-reader-floor-editor"></textarea>' in floor_editor_block
    assert '<div class="chat-reader-panel-title">显示预览</div>' in floor_editor_block
    assert '<textarea x-model="editingMessageDraft" readonly class="form-textarea chat-reader-floor-editor chat-reader-floor-editor--raw"></textarea>' in floor_editor_block


def test_chat_grid_open_floor_editor_seeds_primary_editor_from_raw_message_only():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')
    open_floor_editor_block = extract_js_function_block(chat_grid_source, 'openFloorEditor(message) {')

    assert "this.editingMessageRawDraft = String(message.mes || '');" in open_floor_editor_block
    assert "this.editingMessageDraft = this.extractDisplayContent(this.editingMessageRawDraft);" in open_floor_editor_block
    assert "this.editingMessageDraft = String(message.content || message.mes || '');" not in open_floor_editor_block


def test_chat_grid_save_floor_edit_persists_raw_message_and_rebuilds_rendered_reader_state():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')
    save_floor_edit_block = extract_js_function_block(chat_grid_source, 'async saveFloorEdit() {')

    assert "target.mes = String(this.editingMessageRawDraft || '');" in save_floor_edit_block
    assert 'focusFloor: this.editingFloor,' in save_floor_edit_block
    assert 'this.rebuildActiveChatMessages(runtimeConfig);' in chat_grid_source
    assert 'await this.setReaderWindowAroundFloor(focusFloor || 1, \'center\');' in chat_grid_source


def test_chat_reader_css_mobile_stacks_floor_editor_sections_and_resets_note_overlap_spacing():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    mobile_block = extract_media_block(chat_reader_css, '@media (max-width: 720px)')

    assert '.chat-reader-editor-grid--editor {' in mobile_block
    assert 'display: flex !important;' in mobile_block
    assert 'flex-direction: column !important;' in mobile_block
    assert '.chat-reader-editor-section--narrow,' in mobile_block
    assert '.chat-reader-editor-section--wide {' in mobile_block
    assert 'width: 100%;' in mobile_block
    assert 'flex: 0 0 auto;' in mobile_block
    assert '.chat-reader-editor-note {' in mobile_block
    assert 'margin-top: 0;' in mobile_block


def test_chat_grid_tracks_mobile_header_visibility_state_for_scroll_hiding():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert 'readerMobileHeaderHidden:' in chat_grid_source
    assert 'readerLastScrollTop:' in chat_grid_source
    assert 'readerMobileHeaderHidden = true' in chat_grid_source
    assert 'readerMobileHeaderHidden = false' in chat_grid_source


def test_chat_reader_template_binds_mobile_header_hidden_class():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert "'is-' + readerResponsiveMode + ((readerResponsiveMode === 'mobile' && readerMobileHeaderHidden) ? ' is-mobile-hidden' : '')" in reader_template


def test_chat_reader_template_desktop_header_exposes_independent_tools_search_and_navigator_toggles():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert "@click=\"toggleReaderPanel('left')\">工具</button>" in reader_template
    assert "@click=\"openReaderDesktopPanel('search')\">搜索</button>" in reader_template
    assert "@click=\"openReaderDesktopPanel('navigator')\">导航</button>" in reader_template
    assert "x-show=\"readerResponsiveMode !== 'mobile'\"" in reader_template


def test_chat_grid_reader_desktop_panel_controls_close_only_the_target_panel():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert "const isSamePanelOpen = this.readerShowRightPanel && this.readerRightTab === nextTab;" in chat_grid_source
    assert "this.readerShowRightPanel = false;" in chat_grid_source
    assert "this.readerRightTab = nextTab;" in chat_grid_source
    assert 'closeReaderRightPanel() {' in chat_grid_source
    close_right_section = chat_grid_source.split('closeReaderRightPanel() {', 1)[1].split('}', 1)[0]
    assert 'this.readerShowLeftPanel = false;' not in close_right_section


def test_chat_reader_template_right_close_button_uses_desktop_specific_close_logic():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert '@click="closeReaderRightPanel()"' in reader_template
    assert '@click="hideReaderPanels()"' not in reader_template.split('class="chat-reader-right custom-scrollbar"', 1)[1].split('</aside>', 1)[0]


def test_chat_grid_reader_pane_styles_reflow_center_when_left_panel_closes():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    assert "return 'grid-column: 1;';" in chat_grid_source
    assert "return 'grid-column: 2;';" in chat_grid_source
    assert "return 'grid-column: 3;';" in chat_grid_source


def test_chat_reader_template_binds_desktop_pane_visibility_to_inline_display_styles():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert ":style=" in reader_template
    assert ':style="readerLeftPaneStyle"' in reader_template
    assert ':style="readerRightPaneStyle"' in reader_template


def test_chat_grid_reader_mobile_mode_is_not_only_ua_driven():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')
    layout_source = read_project_file('static/js/components/layout.js')

    assert 'readerResponsiveMode' in chat_grid_source
    assert 'window.innerWidth < 900' in layout_source
    assert 'window.innerWidth < 1180' in layout_source


def test_layout_recomputes_global_device_type_on_window_resize():
    layout_source = read_project_file('static/js/components/layout.js')

    assert "window.addEventListener('resize', () => {" in layout_source
    assert 'this.reDeviceType();' in layout_source


def test_chat_grid_keeps_right_panel_layout_during_app_stage():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    desktop_panel_block = chat_grid_source.split('get readerDesktopRightPanelOpen() {', 1)[1].split('}', 1)[0]
    body_grid_block = chat_grid_source.split('get readerBodyGridStyle() {', 1)[1].split('openReaderDesktopPanel(panel) {', 1)[0]

    assert 'return this.readerShowRightPanel;' in desktop_panel_block
    assert '!this.readerAppMode' not in desktop_panel_block
    assert 'if (this.readerShowRightPanel && !this.readerAppMode)' not in body_grid_block
    assert 'if (this.readerShowRightPanel) {' in body_grid_block


def test_chat_reader_template_keeps_app_stage_in_center_pane_with_separate_right_rail():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')
    shell = extract_chat_reader_shell(reader_template)

    main_section = shell.split('<main class="chat-reader-center custom-scrollbar" :style="readerCenterPaneStyle" @scroll.passive="handleReaderScroll()">', 1)[1].split('</main>', 1)[0]
    right_section = shell.split('<aside x-show="readerShowRightPanel" class="chat-reader-right custom-scrollbar" :style="readerRightPaneStyle">', 1)[1].split('</aside>', 1)[0]

    assert 'chat-reader-app-stage' in main_section
    assert 'chatAppStageHost' in main_section
    assert 'chat-reader-app-stage' not in right_section


def test_chat_reader_template_uses_compact_regex_summary_with_help_entry():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')

    assert 'chat-reader-regex-summary-strip' in reader_template
    assert 'chat-reader-regex-summary-grid' in reader_template
    assert '@click="openRegexHelp()"' in reader_template
    assert 'aria-label="聊天解析规则帮助"' in reader_template
    assert 'chat-reader-regex-source-grid' not in reader_template


def test_chat_grid_tracks_regex_help_modal_state():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')

    open_help_block = extract_js_function_block(chat_grid_source, 'openRegexHelp() {')
    close_help_block = extract_js_function_block(chat_grid_source, 'closeRegexHelp() {')
    close_regex_block = extract_js_function_block(chat_grid_source, 'closeRegexConfig() {')

    assert 'regexHelpOpen: false,' in chat_grid_source
    assert 'openRegexHelp() {' in chat_grid_source
    assert 'closeRegexHelp() {' in chat_grid_source
    assert 'this.regexHelpOpen = true;' in open_help_block
    assert 'this.regexHelpOpen = false;' in close_help_block
    assert 'this.regexHelpOpen = false;' in close_regex_block


def test_chat_reader_css_adds_regex_summary_and_help_modal_primitives():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')

    assert '.chat-reader-regex-summary-strip' in chat_reader_css
    assert '.chat-reader-regex-summary-grid' in chat_reader_css
    assert '.chat-reader-regex-help-button' in chat_reader_css
    assert '.chat-reader-regex-help-modal' in chat_reader_css


def test_chat_reader_template_keeps_regex_summary_dense_without_instructional_copy():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')
    summary_section = reader_template.split('chat-reader-regex-summary-strip', 1)[1].split('<div class="chat-reader-editor-grid', 1)[0]

    assert '精简显示规则来源与草稿状态，详细解释放到帮助里。' not in summary_section
    assert '左侧“当前实际生效规则”会实时预览当前草稿合并后的结果；只有保存后才会真正写回聊天文件。' not in summary_section
    assert 'x-text="regexDraftOutcomeSummary"' not in summary_section
    assert 'chat-reader-regex-summary-feedback' in summary_section


def test_chat_grid_does_not_seed_regex_summary_with_default_instruction_status():
    chat_grid_source = read_project_file('static/js/components/chatGrid.js')
    open_regex_block = extract_js_function_block(chat_grid_source, 'openRegexConfig() {')

    assert "this.regexConfigStatus = '';" in open_regex_block
    assert '测试区默认不自动加载内容，按需手动载入当前定位楼层即可。' not in open_regex_block


def test_chat_reader_css_replaces_tall_regex_status_stack_with_optional_feedback_row():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')

    assert '.chat-reader-regex-summary-feedback' in chat_reader_css
    assert '.chat-reader-regex-summary-status' not in chat_reader_css


def test_chat_reader_scroll_disclosures_use_compact_chip_like_summaries_before_expansion():
    chat_reader_css = read_project_file('static/css/modules/view-chats.css')
    reasoning_block = extract_exact_css_block(
        chat_reader_css,
        '.chat-message-reasoning-summary,\n.chat-message-code-collapse-toggle',
    )
    body_block = extract_exact_css_block(chat_reader_css, '.chat-message-reasoning-body')

    assert 'display: inline-flex;' in reasoning_block
    assert 'align-items: center;' in reasoning_block
    assert 'min-height: 28px;' in reasoning_block
    assert 'border-radius: 999px;' in reasoning_block
    assert 'width: fit-content;' in reasoning_block
    assert 'padding: 0.22rem 0.68rem;' in reasoning_block
    assert 'background: color-mix(in srgb, var(--bg-sub), transparent 8%);' in reasoning_block
    assert 'border-top: 1px solid' in body_block


def test_mobile_header_template_uses_title_block_for_sidebar_and_search_upload_cluster():
    header_template = read_project_file('templates/components/header.html')

    assert '@click="openMobileSidebar()"' in header_template
    assert 'class="mobile-search-group"' in header_template
    assert 'x-show="showMobileUploadButton"' in header_template
    assert '@click="triggerMobileUpload()"' in header_template


def test_mobile_sidebar_template_removes_floating_button_group_and_keeps_single_hidden_input():
    sidebar_template = read_project_file('templates/components/sidebar.html')

    assert 'class="sidebar-button-group"' not in sidebar_template
    assert 'sidebar-group-btn' not in sidebar_template
    assert sidebar_template.count('x-data="sidebar"') == 1
    assert sidebar_template.count('x-ref="mobileImportInput"') == 1


def test_mobile_header_script_defines_upload_trigger_contract():
    header_source = read_project_file('static/js/components/header.js')
    header_template = read_project_file('templates/components/header.html')

    assert "const MOBILE_HEADER_UPLOAD_MODES = ['cards', 'worldinfo', 'presets', 'regex', 'scripts', 'quick_replies'];" in header_source
    show_mobile_upload_block = extract_js_function_block(header_source, 'get showMobileUploadButton()')
    assert "this.deviceType === 'mobile'" in show_mobile_upload_block
    assert 'MOBILE_HEADER_UPLOAD_MODES.includes(this.currentMode)' in show_mobile_upload_block
    assert "window.dispatchEvent(new CustomEvent('request-mobile-upload'));" in header_source
    assert '@click="triggerChatImport(); closeMobileMenu()"' in header_template


def test_mobile_header_script_closes_menu_before_sidebar_and_upload_actions():
    header_source = read_project_file('static/js/components/header.js')

    assert 'openMobileSidebar()' in header_source
    assert 'this.closeMobileMenu();' in extract_js_function_block(header_source, 'openMobileSidebar()')
    assert 'const nextVisible = !this.$store.global.visibleSidebar;' in extract_js_function_block(header_source, 'openMobileSidebar()')
    assert 'this.$store.global.visibleSidebar = nextVisible;' in extract_js_function_block(header_source, 'openMobileSidebar()')
    assert "document.body.style.overflow = nextVisible ? 'hidden' : '';" in extract_js_function_block(header_source, 'openMobileSidebar()')
    assert 'triggerMobileUpload()' in header_source
    assert 'this.closeMobileMenu();' in extract_js_function_block(header_source, 'triggerMobileUpload()')


def test_mobile_sidebar_script_listens_for_upload_trigger_and_cleans_up():
    sidebar_source = read_project_file('static/js/components/sidebar.js')

    assert "window.addEventListener('request-mobile-upload', this.handleMobileUploadRequest);" in sidebar_source
    assert "window.removeEventListener('request-mobile-upload', this.handleMobileUploadRequest);" in sidebar_source
    handle_upload_block = extract_js_function_block(sidebar_source, 'handleMobileUploadRequest()')
    assert "this.currentMode === 'chats'" in handle_upload_block
    assert '!this.$refs.mobileImportInput' in handle_upload_block
    assert 'this.$refs.mobileImportInput.click();' in handle_upload_block


def test_mobile_layout_css_defines_search_upload_group_and_no_legacy_sidebar_button_group_rules():
    layout_css = read_project_file('static/css/modules/layout.css')

    assert '.mobile-search-group {' in layout_css
    assert '.mobile-upload-btn {' in layout_css
    assert '.mobile-header-left {' in layout_css
    assert '.sidebar-button-group {' not in layout_css
    assert '.sidebar-group-btn {' not in layout_css


def test_mobile_header_template_tracks_sidebar_open_state_for_toggle_feedback():
    header_template = read_project_file('templates/components/header.html')

    assert ":class=\"{ 'is-active': $store.global.visibleSidebar }\"" in header_template
    assert ":aria-pressed=\"$store.global.visibleSidebar ? 'true' : 'false'\"" in header_template


def test_mobile_header_script_toggles_sidebar_visibility_and_scroll_lock():
    header_source = read_project_file('static/js/components/header.js')
    sidebar_toggle_block = extract_js_function_block(header_source, 'openMobileSidebar()')

    assert 'const nextVisible = !this.$store.global.visibleSidebar;' in sidebar_toggle_block
    assert 'this.$store.global.visibleSidebar = nextVisible;' in sidebar_toggle_block
    assert "document.body.style.overflow = nextVisible ? 'hidden' : '';" in sidebar_toggle_block


def test_mobile_layout_css_defines_mobile_header_toggle_feedback_states():
    layout_css = read_project_file('static/css/modules/layout.css')
    active_block = extract_exact_css_block(layout_css, '.mobile-header-left:active')
    open_block = extract_exact_css_block(layout_css, '.mobile-header-left.is-active')

    assert 'background-color: var(--bg-hover);' in active_block
    assert 'transform: scale(0.98);' in active_block
    assert 'background-color: var(--accent-faint);' in open_block
    assert 'border-color: var(--accent-light);' in open_block


def test_card_sidebar_template_adds_stable_split_layout_hooks():
    sidebar_template = read_project_file('templates/components/sidebar.html')

    assert 'class="flex-1 card-sidebar-shell"' in sidebar_template
    assert 'class="card-sidebar-categories"' in sidebar_template
    assert 'class="card-sidebar-tags"' in sidebar_template
    assert 'class="sidebar-section-header card-sidebar-tags-header"' in sidebar_template
    assert 'class="sidebar-content custom-scrollbar card-sidebar-tags-body"' in sidebar_template


def test_card_sidebar_template_removes_expansion_only_lower_pane_layout_styles():
    sidebar_template = read_project_file('templates/components/sidebar.html')

    assert ":style=\"tagsSectionExpanded ? 'flex: 1;' : ''\"" not in sidebar_template
    assert 'style="display: flex; flex-direction: column; overflow: hidden;"' not in sidebar_template
    assert 'x-show="tagsSectionExpanded" class="sidebar-content custom-scrollbar card-sidebar-tags-body"' in sidebar_template


def test_card_sidebar_and_pagination_templates_add_empty_state_and_mobile_wrap_hooks():
    sidebar_template = read_project_file('templates/components/sidebar.html')
    cards_template = read_project_file('templates/components/grid_cards.html')

    assert 'class="card-sidebar-empty-state"' in sidebar_template
    assert 'class="card-pagination-summary"' in cards_template
    assert 'class="card-pagination-controls card-pagination-page-cluster"' in cards_template
    assert 'class="card-pagination-controls" style="display: flex; align-items: center; gap: 0.5rem;"' not in cards_template


def test_card_sidebar_layout_css_defines_persistent_strip_and_scoped_solid_surfaces():
    layout_css = read_project_file('static/css/modules/layout.css')

    assert '.card-sidebar-shell {' in layout_css
    assert '.card-sidebar-tags {' in layout_css
    assert 'height: 3.25rem;' in extract_exact_css_block(layout_css, '.card-sidebar-tags.is-collapsed')
    expanded_block = extract_exact_css_block(layout_css, '.card-sidebar-tags.is-expanded')
    assert 'flex: 0 0 clamp(10rem, 34%, 15rem);' in expanded_block
    assert 'max-height: 45%;' in expanded_block
    assert '.card-sidebar-shell .sidebar-content {' in layout_css
    assert '.card-sidebar-shell .sidebar-section-header {' in layout_css


def test_card_pagination_css_keeps_mobile_footer_compact_with_safe_area_spacing():
    cards_css = read_project_file('static/css/modules/view-cards.css')
    mobile_cards_css = extract_media_block(cards_css, '@media (max-width: 768px)')

    assert '.card-pagination-summary {' in cards_css
    assert '.card-pagination-page-cluster {' in cards_css
    assert 'padding-bottom: calc(0.5rem + env(safe-area-inset-bottom, 0px));' in cards_css
    assert '.card-flip-toolbar {' in mobile_cards_css
    assert 'flex-wrap: nowrap;' in mobile_cards_css
    assert '.card-pagination-page-cluster {' in mobile_cards_css
    assert 'min-width: 0;' in cards_css


def test_base_css_stabilizes_mobile_text_inflation_and_dynamic_viewport_height():
    base_css = read_project_file('static/css/modules/base.css')
    body_block = extract_exact_css_block(base_css, 'body')
    body_lines = {line.strip() for line in body_block.splitlines() if line.strip()}

    assert 'text-size-adjust: 100%;' in base_css
    assert '-webkit-text-size-adjust: 100%;' in base_css
    assert 'min-height: 100vh;' in base_css
    assert 'min-height: 100dvh;' in base_css
    assert 'height: 100vh;' in body_lines
    assert 'height: 100dvh;' in body_lines
    assert 'height: auto;' not in body_lines


def test_global_state_syncs_visual_viewport_height_into_css_variable():
    state_source = read_project_file('static/js/state.js')

    assert 'syncViewportHeight() {' in state_source
    sync_block = extract_js_function_block(state_source, 'syncViewportHeight() {')
    init_block = extract_js_function_block(state_source, 'init() {')

    assert 'window.visualViewport' in sync_block
    assert 'window.visualViewport.height' in sync_block
    assert "updateCssVariable('--app-viewport-height'" in sync_block
    assert "updateCssVariable('--app-viewport-height-safe'" in sync_block
    assert 'window.innerHeight || 0' in sync_block
    assert 'Math.max(0, roundedHeight - 1)' in sync_block
    assert 'this.syncViewportHeight();' in init_block
    assert "window.visualViewport.addEventListener('resize', this._visualViewportResizeHandler" in init_block
    assert "window.addEventListener('orientationchange', this._visualViewportResizeHandler" in init_block


def test_mobile_modal_components_css_defines_shared_fullscreen_dynamic_viewport_baseline():
    components_css = read_project_file('static/css/modules/components.css')
    assert '@media (max-width: 768px)' in components_css
    mobile_components_css = extract_media_block(components_css, '@media (max-width: 768px)')

    assert '.modal-overlay {' in mobile_components_css
    assert '.modal-container {' in mobile_components_css
    overlay_block = extract_exact_css_block(mobile_components_css, '.modal-overlay')
    container_block = extract_exact_css_block(mobile_components_css, '.modal-container')

    assert 'padding: 0;' in overlay_block
    assert 'align-items: stretch;' in overlay_block
    assert 'justify-content: flex-start;' in overlay_block
    assert 'overflow: hidden;' in overlay_block

    assert 'width: 100vw;' in container_block
    assert 'max-width: 100vw;' in container_block
    assert 'height: 100vh;' in container_block
    assert 'height: var(--app-viewport-height-safe, var(--app-viewport-height, 100dvh));' in container_block
    assert 'height: 100dvh;' in container_block
    assert 'min-height: var(--app-viewport-height-safe, var(--app-viewport-height, 100dvh));' in container_block
    assert container_block.index('height: 100dvh;') < container_block.index('height: var(--app-viewport-height-safe, var(--app-viewport-height, 100dvh));')
    assert 'border-radius: 0;' in container_block


def test_detail_modal_mobile_css_uses_dynamic_viewport_and_safe_area_spacing():
    detail_css = read_project_file('static/css/modules/modal-detail.css')
    mobile_detail_css = extract_media_block(detail_css, '@media (max-width: 768px)')

    detail_modal_block = extract_exact_css_block(mobile_detail_css, '.detail-modal')
    detail_toolbar_block = extract_exact_css_block(mobile_detail_css, '.detail-left-toolbar')
    detail_zoombar_block = extract_exact_css_block(mobile_detail_css, '.detail-zoombar')
    detail_content_block = extract_exact_css_block(mobile_detail_css, '.detail-content')

    assert 'width: 100vw;' in detail_modal_block
    assert 'height: 100vh;' in detail_modal_block
    assert 'height: var(--app-viewport-height-safe, var(--app-viewport-height, 100dvh));' in detail_modal_block
    assert 'height: 100dvh;' in detail_modal_block
    assert 'min-height: var(--app-viewport-height-safe, var(--app-viewport-height, 100dvh));' in detail_modal_block
    assert detail_modal_block.index('height: 100dvh;') < detail_modal_block.index('height: var(--app-viewport-height-safe, var(--app-viewport-height, 100dvh));')
    assert 'max-width: 100vw;' in detail_modal_block
    assert 'margin: 0 !important;' in detail_modal_block
    assert 'top: calc(env(safe-area-inset-top, 0px) + 0.5rem);' in detail_toolbar_block
    assert 'bottom: calc(env(safe-area-inset-bottom, 0px) + 0.5rem);' in detail_zoombar_block
    assert 'padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 1rem);' in detail_content_block


def test_mobile_tool_and_custom_modal_variants_prefer_dynamic_viewport_height():
    tools_css = read_project_file('static/css/modules/modal-tools.css')
    settings_css = read_project_file('static/css/modules/modal-settings.css')
    automation_css = read_project_file('static/css/modules/modal-automation.css')

    mobile_tools_css = extract_media_block(tools_css, '@media (max-width: 768px)')
    mobile_settings_css = extract_media_block(settings_css, '@media (max-width: 768px)')
    mobile_automation_css = extract_media_block(automation_css, '@media (max-width: 768px)')

    assert '.advanced-editor-container {' in mobile_tools_css
    assert '.advanced-editor-header {' in mobile_tools_css
    assert '.advanced-editor-footer {' in mobile_tools_css
    assert '.adv-split-view {' in mobile_tools_css
    assert '.adv-editor-pane {' in mobile_tools_css
    assert '.large-editor-container {' in mobile_tools_css
    advanced_editor_block = extract_exact_css_block(mobile_tools_css, '.advanced-editor-container')
    advanced_header_block = extract_exact_css_block(mobile_tools_css, '.advanced-editor-header')
    advanced_footer_block = extract_exact_css_block(mobile_tools_css, '.advanced-editor-footer')
    advanced_split_block = extract_exact_css_block(mobile_tools_css, '.adv-split-view')
    advanced_editor_pane_block = extract_exact_css_block(mobile_tools_css, '.adv-editor-pane')
    large_editor_block = extract_exact_css_block(mobile_tools_css, '.large-editor-container')
    settings_block = extract_exact_css_block(mobile_settings_css, '.settings-modal-container')
    automation_block = extract_exact_css_block(mobile_automation_css, '.automation-container')

    assert 'height: 100dvh !important;' in advanced_editor_block
    assert 'height: var(--app-viewport-height-safe, var(--app-viewport-height, 100dvh)) !important;' in advanced_editor_block
    assert 'min-height: var(--app-viewport-height-safe, var(--app-viewport-height, 100dvh));' in advanced_editor_block
    assert advanced_editor_block.index('height: 100dvh !important;') < advanced_editor_block.index('height: var(--app-viewport-height-safe, var(--app-viewport-height, 100dvh)) !important;')
    assert 'padding-top: calc(env(safe-area-inset-top, 0px) + 0.75rem) !important;' in advanced_header_block
    assert 'padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 0.75rem) !important;' in advanced_footer_block
    assert 'min-height: 0;' in advanced_split_block
    assert 'min-height: 0;' in advanced_editor_pane_block
    assert '-webkit-overflow-scrolling: touch;' in advanced_editor_pane_block

    assert 'height: 100dvh !important;' in large_editor_block
    assert 'height: var(--app-viewport-height-safe, var(--app-viewport-height, 100dvh)) !important;' in large_editor_block
    assert 'min-height: var(--app-viewport-height-safe, var(--app-viewport-height, 100dvh));' in large_editor_block
    assert 'height: var(--app-viewport-height-safe, var(--app-viewport-height, 100dvh));' in settings_block
    assert 'height: 100dvh;' in settings_block
    assert 'min-height: var(--app-viewport-height-safe, var(--app-viewport-height, 100dvh));' in settings_block
    assert 'height: 100dvh !important;' in automation_block
    assert 'height: var(--app-viewport-height-safe, var(--app-viewport-height, 100dvh)) !important;' in automation_block
    assert 'min-height: var(--app-viewport-height-safe, var(--app-viewport-height, 100dvh)) !important;' in automation_block


def test_automation_modal_template_exposes_new_action_options_and_structured_inputs():
    automation_template = read_project_file('templates/modals/automation.html')
    rename_block = automation_template.split("action.type === 'rename_file_by_template'", 1)[1].split('</template>', 1)[0]
    split_block = automation_template.split("action.type === 'split_category_to_tags'", 1)[1].split('</template>', 1)[0]

    assert '<option value="rename_file_by_template">🧩 模板重命名文件</option>' in automation_template
    assert '<option value="split_category_to_tags">📝 分类拆分为标签</option>' in automation_template
    assert "action.type === 'rename_file_by_template'" in automation_template
    assert "action.type === 'split_category_to_tags'" in automation_template
    assert 'x-model="cfg.template"' in rename_block
    assert 'x-model="cfg.fallback_template"' in rename_block
    assert 'x-model.number="cfg.max_length"' in rename_block
    assert 'x-model="cfg.exclude_category_tags"' not in rename_block
    assert 'x-model="cfg.exclude_category_tags"' in split_block
    assert '排除分类标签:' in split_block
    assert '当前分类路径会自动按 / 拆分' in split_block
    assert '回退模板:' not in split_block
    assert '最大长度:' not in split_block
    assert '@change="initActionConfig(action)"' in automation_template
    assert 'x-data="{ cfg: initActionConfig(action) }"' in automation_template
    assert "action.type === 'fetch_forum_tags'" in automation_template
    assert "action.config = { template: '', fallback_template: '', max_length: 120, exclude_category_tags: '' }" not in automation_template


def test_automation_modal_js_centralizes_template_action_config_and_removes_duplicate_methods():
    automation_js = read_project_file('static/js/components/automationModal.js')

    assert "const TEMPLATE_ACTION_TYPES = ['rename_file_by_template', 'split_category_to_tags'];" in automation_js
    assert 'function createRenameTemplateConfig(value = {}) {' in automation_js
    assert 'function createSplitCategoryTagsConfig(value = {}) {' in automation_js
    assert "action.type === 'rename_file_by_template'" in automation_js
    assert "action.type === 'split_category_to_tags'" in automation_js
    assert 'createRenameTemplateConfig(rawValue)' in automation_js
    assert 'createSplitCategoryTagsConfig(rawValue)' in automation_js
    assert 'createRenameTemplateConfig(action.config || action.value || {})' in automation_js
    assert 'createSplitCategoryTagsConfig(action.config || action.value || {})' in automation_js
    assert automation_js.count('deleteRule(index) {') == 1
    assert automation_js.count('moveRule(index, dir) {') == 1


def test_automation_help_modal_uses_four_tab_structure_with_new_guidance():
    automation_template = read_project_file('templates/modals/automation.html')

    assert 'automation-help-tabs' in automation_template
    assert 'automation-help-panel' in automation_template
    assert 'helpActiveTab' in automation_template
    assert 'role="tablist"' in automation_template

    tab_specs = (
        ('conditions', '条件'),
        ('actions', '动作'),
        ('triggers', '触发时机'),
        ('templates', '模板语法'),
    )

    for tab_key, tab_label in tab_specs:
        assert tab_label in automation_template
        assert f'role="tab"' in automation_template
        assert f'id="automation-help-tab-{tab_key}"' in automation_template
        assert f'aria-controls="automation-help-panel-{tab_key}"' in automation_template
        assert f"x-show=\"helpActiveTab === '{tab_key}'\"" in automation_template
        assert f'role="tabpanel"' in automation_template
        assert f'id="automation-help-panel-{tab_key}"' in automation_template
        assert f'aria-labelledby="automation-help-tab-{tab_key}"' in automation_template

    assert 'rename_file_by_template' in automation_template
    assert 'split_category_to_tags' in automation_template
    assert '不同触发场景只会运行对应的动作子集' in automation_template
    assert '导入时会跳过抓取论坛标签与标签合并' in automation_template
    assert '更新链接时只执行抓取论坛标签' in automation_template
    assert '手动打标时只执行标签合并' in automation_template
    assert '{% raw %}{{char_name}} - {{char_version|version}} - {{import_date|date:%Y-%m-%d}}{% endraw %}' in automation_template
    assert '支持字段：char_name、char_version、filename、filename_stem、category、import_time、import_date、modified_time、modified_date' in automation_template
    assert '日期字段支持 date 过滤器' in automation_template
    assert 'date:%Y-%m-%d' in automation_template
    assert 'date:%Y%m%d' in automation_template
    assert 'category = a/b/c  ->  tags += [a, b, c]' in automation_template
    assert 'split_category_to_tags' in automation_template
    assert '不读取模板' in automation_template
    assert '不会使用回退模板或最大长度' in automation_template


def test_automation_help_modal_lists_filter_examples_for_non_jinja_users():
    automation_template = read_project_file('templates/modals/automation.html')

    assert 'automation-template-field-grid' in automation_template
    assert 'automation-template-filter-list' in automation_template
    assert 'trim：去掉首尾空格' in automation_template
    assert 'default：为空时使用备用值' in automation_template
    assert 'limit：截断过长文本' in automation_template
    assert 'date：格式化导入时间或修改时间' in automation_template
    assert 'version：从版本文本里提取主版本号' in automation_template
    assert '{% raw %}{{char_name|trim}}{% endraw %}' in automation_template
    assert '{% raw %}{{char_version|default:unknown}}{% endraw %}' in automation_template
    assert '{% raw %}{{filename_stem|limit:20}}{% endraw %}' in automation_template
    assert '{% raw %}{{import_date|date:%Y-%m-%d}}{% endraw %}' in automation_template
    assert '{% raw %}{{char_version|version}}{% endraw %}' in automation_template


def test_automation_help_modal_uses_reference_card_layout_for_fields_and_filters():
    automation_template = read_project_file('templates/modals/automation.html')
    automation_css = read_project_file('static/css/modules/modal-automation.css')

    assert 'automation-template-reference-grid' in automation_template
    assert 'automation-template-reference-column' in automation_template
    assert 'automation-template-field-grid' in automation_template
    assert 'automation-template-filter-list' in automation_template
    assert '.automation-template-reference-grid' in automation_css
    assert '.automation-template-reference-column' in automation_css
    assert '.automation-template-field-grid' in automation_css
    assert '.automation-template-filter-list' in automation_css


def test_automation_help_modal_includes_template_quick_reference_cheatsheet():
    automation_template = read_project_file('templates/modals/automation.html')

    assert 'automation-template-cheatsheet' in automation_template
    assert '字段写法：' in automation_template
    assert '{% raw %}{{field}}{% endraw %}' in automation_template
    assert '过滤器写法：' in automation_template
    assert '{% raw %}{{field|filter}}{% endraw %}' in automation_template
    assert '带参数过滤器：' in automation_template
    assert '{% raw %}{{field|filter:param}}{% endraw %}' in automation_template


def test_rename_template_action_exposes_quick_fill_example_buttons():
    automation_template = read_project_file('templates/modals/automation.html')
    automation_js = read_project_file('static/js/components/automationModal.js')

    assert '套用示例' in automation_template
    assert '角色名 + 版本' in automation_template
    assert '角色名 + 导入日期' in automation_template
    assert '角色名 + 版本 + 修改日期' in automation_template
    assert 'applyRenameTemplatePreset(action, ' in automation_template
    assert 'applyRenameTemplatePreset(action, preset)' in automation_js
    assert "preset === 'name_version'" in automation_js
    assert "preset === 'name_import_date'" in automation_js
    assert "preset === 'name_version_modified_date'" in automation_js


def test_automation_help_modal_template_examples_are_jinja_safe_literals():
    automation_template = read_project_file('templates/modals/automation.html')

    assert '<code class="font-mono">{{...}}</code>' not in automation_template
    assert '<div class="bg-[var(--bg-code)] p-2 rounded text-xs font-mono">{{char_name}} - {{creator}}</div>' not in automation_template
    assert '<div class="bg-[var(--bg-code)] p-2 rounded text-xs font-mono">{{tags}}</div>' not in automation_template
    assert '{% raw %}{{...}}{% endraw %}' in automation_template
    assert '{% raw %}{{char_name}} - {{char_version|version}} - {{import_date|date:%Y-%m-%d}}{% endraw %}' in automation_template
    assert 'category = a/b/c  ->  tags += [a, b, c]' in automation_template


def test_automation_help_modal_js_and_css_define_tab_state_and_mobile_layout():
    automation_js = read_project_file('static/js/components/automationModal.js')
    automation_css = read_project_file('static/css/modules/modal-automation.css')
    close_modal_block = extract_js_function_block(automation_js, 'closeModal() {')

    assert "helpActiveTab: 'conditions'" in automation_js
    assert 'openHelpTab(tab)' in automation_js
    assert 'showHelpModal = true' in automation_js
    assert "this.helpActiveTab = tab;" in automation_js
    assert "this.helpActiveTab = 'conditions';" in close_modal_block
    assert 'this.showHelpModal = false;' in close_modal_block

    for selector in (
        '.automation-help-tabs',
        '.automation-help-tab',
        '.automation-help-panel',
    ):
        assert selector in automation_css

    mobile_block = extract_media_block(automation_css, '@media (max-width: 768px)')
    help_tab_block = extract_exact_css_block(automation_css, '.automation-help-tab')
    active_tab_block = extract_exact_css_block(automation_css, '.automation-help-tab.is-active')
    mobile_tabs_block = extract_exact_css_block(mobile_block, '.automation-help-tabs')
    mobile_tab_block = extract_exact_css_block(mobile_block, '.automation-help-tab')

    assert 'border:' in help_tab_block
    assert 'transition:' in help_tab_block
    assert 'border-color: var(--accent-main);' in active_tab_block
    assert 'color: var(--text-main);' in active_tab_block
    assert 'flex-wrap: wrap' in mobile_tabs_block
    assert 'width: 100%' in mobile_tab_block or 'flex: 1 1' in mobile_tab_block


def test_automation_modal_template_exposes_sort_controls_for_groups_conditions_and_actions():
    automation_template = read_project_file('templates/modals/automation.html')

    assert '@click="moveGroup(rIdx, gIdx, -1)"' in automation_template
    assert '@click="moveGroup(rIdx, gIdx, 1)"' in automation_template
    assert '@click="moveConditionInGroup(rIdx, gIdx, cIdx, -1)"' in automation_template
    assert '@click="moveConditionInGroup(rIdx, gIdx, cIdx, 1)"' in automation_template
    assert '@click="moveAction(rIdx, aIdx, -1)"' in automation_template
    assert '@click="moveAction(rIdx, aIdx, 1)"' in automation_template
    assert 'title="上移条件组"' in automation_template
    assert 'title="下移条件组"' in automation_template
    assert 'title="上移条件"' in automation_template
    assert 'title="下移条件"' in automation_template
    assert 'title="上移动作"' in automation_template
    assert 'title="下移动作"' in automation_template
    assert 'automation-inline-actions' in automation_template


def test_automation_modal_js_exposes_reusable_move_helpers_for_nested_rule_items():
    automation_js = read_project_file('static/js/components/automationModal.js')
    move_rule_block = extract_js_function_block(automation_js, 'moveRule(index, dir) {')
    move_group_block = extract_js_function_block(automation_js, 'moveGroup(ruleIdx, groupIdx, dir) {')
    move_condition_block = extract_js_function_block(automation_js, 'moveConditionInGroup(ruleIdx, groupIdx, condIdx, dir) {')
    move_action_block = extract_js_function_block(automation_js, 'moveAction(ruleIdx, actIdx, dir) {')

    assert 'moveArrayItem(items, index, dir) {' in automation_js
    assert 'moveRule(index, dir) {' in automation_js
    assert 'moveGroup(ruleIdx, groupIdx, dir) {' in automation_js
    assert 'moveConditionInGroup(ruleIdx, groupIdx, condIdx, dir) {' in automation_js
    assert 'moveAction(ruleIdx, actIdx, dir) {' in automation_js
    assert 'this.moveArrayItem(this.editingRules, index, dir)' in move_rule_block
    assert 'this.moveArrayItem(groups, groupIdx, dir)' in move_group_block
    assert 'this.moveArrayItem(conditions, condIdx, dir)' in move_condition_block
    assert 'this.moveArrayItem(actions, actIdx, dir)' in move_action_block


def test_automation_modal_css_keeps_inline_sort_actions_compact_and_wrapping():
    automation_css = read_project_file('static/css/modules/modal-automation.css')
    mobile_block = extract_media_block(automation_css, '@media (max-width: 768px)')
    inline_actions_block = extract_exact_css_block(automation_css, '.automation-inline-actions')
    mobile_inline_actions_block = extract_exact_css_block(mobile_block, '.automation-inline-actions')

    assert 'display: flex;' in inline_actions_block
    assert 'align-items: center;' in inline_actions_block
    assert 'gap:' in inline_actions_block
    assert 'flex-wrap: wrap;' in inline_actions_block
    assert 'justify-content: flex-end;' in inline_actions_block
    assert 'width: 100%;' in mobile_inline_actions_block or 'justify-content: flex-start;' in mobile_inline_actions_block


def test_detail_modal_template_marks_multicard_mobile_tabs_for_stacked_layout():
    detail_template = read_project_file('templates/modals/detail_card.html')

    assert '<section x-show="tab===\'basic\'" x-transition.opacity class="detail-section detail-section-fill detail-section-mobile-stack">' in detail_template
    assert '<section x-show="tab===\'persona\'" x-transition.opacity class="detail-section detail-section-fill detail-section-mobile-stack">' in detail_template
    assert '<section x-show="tab===\'dialog\'" x-transition.opacity class="detail-section detail-section-fill detail-section-mobile-stack">' in detail_template


def test_detail_modal_mobile_css_releases_equal_height_card_splits_for_stacked_tabs():
    detail_css = read_project_file('static/css/modules/modal-detail.css')
    mobile_detail_css = extract_media_block(detail_css, '@media (max-width: 768px)')

    detail_left_block = extract_exact_css_block(mobile_detail_css, '.detail-left')
    stack_section_block = extract_exact_css_block(mobile_detail_css, '.detail-section-mobile-stack')
    stack_scroll_block = extract_exact_css_block(mobile_detail_css, '.detail-section-mobile-stack .detail-tab-scroll')
    stack_card_block = extract_exact_css_block(mobile_detail_css, '.detail-section-mobile-stack .detail-tab-scroll > .detail-card')
    stack_textarea_block = extract_exact_css_block(mobile_detail_css, '.detail-section-mobile-stack .detail-card .form-textarea')
    stack_dialog_block = extract_exact_css_block(mobile_detail_css, '.detail-section-mobile-stack .detail-card .detail-dialog-grow-box')
    stack_large_block = extract_exact_css_block(mobile_detail_css, '.detail-section-mobile-stack .detail-card--lg')
    stack_small_block = extract_exact_css_block(mobile_detail_css, '.detail-section-mobile-stack .detail-card--sm')

    assert 'height: clamp(220px, 34vh, 320px);' in detail_left_block
    assert 'min-height: 220px;' in detail_left_block
    assert 'max-height: 38vh;' in detail_left_block

    assert 'flex: 0 0 auto;' in stack_section_block
    assert 'overflow: visible;' in stack_section_block
    assert 'flex: 0 0 auto;' in stack_scroll_block
    assert 'min-height: auto;' in stack_scroll_block
    assert 'overflow: visible;' in stack_scroll_block
    assert 'padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 0.75rem);' in stack_scroll_block
    assert 'flex: 0 0 auto;' in stack_card_block
    assert 'min-height: auto;' in stack_card_block
    assert 'flex: 0 0 auto;' in stack_textarea_block
    assert 'min-height: clamp(6rem, 18vh, 9rem);' in stack_textarea_block
    assert 'flex: 0 0 auto !important;' in stack_dialog_block
    assert 'min-height: clamp(11rem, 30vh, 16rem) !important;' in stack_dialog_block
    assert 'flex: 0 0 auto !important;' in stack_large_block
    assert 'flex: 0 0 auto !important;' in stack_small_block


def test_detail_modal_mobile_css_uses_border_box_chain_and_parent_relative_inner_shell():
    detail_css = read_project_file('static/css/modules/modal-detail.css')
    detail_modal_block = extract_exact_css_block(detail_css, '.detail-modal')
    detail_inner_block = extract_exact_css_block(detail_css, '.detail-modal-inner')
    mobile_detail_css = extract_media_block(detail_css, '@media (max-width: 768px)')
    mobile_detail_modal_block = extract_exact_css_block(mobile_detail_css, '.detail-modal')
    mobile_detail_inner_block = extract_exact_css_block(mobile_detail_css, '.detail-modal-inner')

    assert 'box-sizing: border-box;' in detail_modal_block
    assert 'box-sizing: border-box;' in detail_inner_block
    assert 'height: 100%;' in detail_inner_block
    assert 'max-height: 100%;' in mobile_detail_modal_block
    assert 'height: 100%;' in mobile_detail_inner_block
    assert 'max-height: 100%;' in mobile_detail_inner_block


def test_mobile_layout_css_keeps_sidebar_shell_scrollable_inside_visual_viewport():
    layout_css = read_project_file('static/css/modules/layout.css')
    mobile_layout_css = extract_media_block(layout_css, '@media (max-width: 768px)')

    sidebar_mobile_block = extract_exact_css_block(layout_css, '.sidebar-mobile')
    assert 'height: 100%;' in sidebar_mobile_block
    assert 'max-height: 100%;' in sidebar_mobile_block
    assert '.sidebar-mobile {' in mobile_layout_css
    assert 'overflow-y: auto;' in mobile_layout_css
    assert '-webkit-overflow-scrolling: touch;' in mobile_layout_css


def test_card_pagination_mobile_css_anchors_bar_with_dynamic_viewport_and_box_sizing():
    cards_css = read_project_file('static/css/modules/view-cards.css')
    mobile_cards_css = extract_media_block(cards_css, '@media (max-width: 768px)')

    assert 'box-sizing: border-box;' in extract_exact_css_block(cards_css, '.card-pagination-bar')
    assert 'max-width: 100%;' in mobile_cards_css
    assert 'box-sizing: border-box;' in mobile_cards_css


def test_card_hover_clarity_css_removes_backdrop_blur_from_tag_text_surfaces():
    cards_css = read_project_file('static/css/modules/view-cards.css')
    tag_block = extract_exact_css_block(cards_css, '.card-image-tags-wrap .card-tag')
    neutral_tag_block = extract_exact_css_block(
        cards_css,
        '.card-image-tags-wrap .card-tag-filter:not(.is-included):not(.is-excluded)',
    )
    light_tag_block = extract_exact_css_block(
        cards_css,
        'html.light-mode .card-image-tags-wrap .card-tag',
    )
    light_neutral_tag_block = extract_exact_css_block(
        cards_css,
        'html.light-mode\n  .card-image-tags-wrap\n  .card-tag-filter:not(.is-included):not(.is-excluded)',
    )

    assert 'backdrop-filter: var(--tag-chip-backdrop);' not in tag_block
    assert '-webkit-backdrop-filter: var(--tag-chip-backdrop);' not in tag_block
    assert 'backdrop-filter: none;' in tag_block
    assert '-webkit-backdrop-filter: none;' in tag_block
    assert 'backdrop-filter: none;' in neutral_tag_block
    assert '-webkit-backdrop-filter: none;' in neutral_tag_block
    assert 'backdrop-filter: var(--tag-chip-backdrop);' not in light_tag_block
    assert '-webkit-backdrop-filter: var(--tag-chip-backdrop);' not in light_tag_block
    assert 'backdrop-filter: none;' in light_tag_block
    assert '-webkit-backdrop-filter: none;' in light_tag_block
    assert 'backdrop-filter: none;' in light_neutral_tag_block
    assert '-webkit-backdrop-filter: none;' in light_neutral_tag_block


def test_card_hover_clarity_css_keeps_back_note_surface_sharp_without_losing_hover_feedback():
    cards_css = read_project_file('static/css/modules/view-cards.css')
    hover_block = extract_exact_css_block(cards_css, '.st-card:hover')
    back_block = extract_exact_css_block(cards_css, '.card-back')
    flipped_back_block = extract_exact_css_block(cards_css, '.card-flip-inner.is-flipped .card-back')
    note_block = extract_exact_css_block(cards_css, '.local-note-preview')

    assert 'transform: translateY(-4px);' in hover_block
    assert 'box-shadow:' in hover_block
    assert 'brightness(0.9) saturate(0.94)' not in back_block
    assert 'brightness(1) saturate(1)' not in flipped_back_block
    assert 'background:' in note_block
    assert 'border: 1px solid' in note_block
    assert '.st-card:hover .card-source-link-fab,' in cards_css
    assert '.st-card:hover .card-fav-overlay,' in cards_css


def test_card_back_mobile_css_allows_local_note_to_fill_remaining_space():
    cards_css = read_project_file('static/css/modules/view-cards.css')
    mobile_cards_css = extract_media_block(cards_css, '@media (max-width: 768px)')
    back_note_block = extract_exact_css_block(mobile_cards_css, '.card-back-note')

    assert 'max-height: 3.2rem;' not in back_note_block
    assert 'max-height: none;' in back_note_block
    assert 'flex: 1 1 auto;' in back_note_block


def test_card_sidebar_template_hides_complete_library_action_until_mobile_tags_panel_expands():
    sidebar_template = read_project_file('templates/components/sidebar.html')

    assert 'x-show="$store.global.deviceType !== \'mobile\' || tagsSectionExpanded"' in sidebar_template


def test_worldinfo_sidebar_template_includes_category_tree_section():
    sidebar_template = read_project_file('templates/components/sidebar.html')

    assert "currentMode === 'worldinfo'" in sidebar_template
    assert '世界书分类' in sidebar_template
    assert 'wiFolderTree' in sidebar_template
    assert 'setWiCategory' in sidebar_template
    assert 'getWiCategoryCount' in sidebar_template
    assert 'getFolderCapabilities' in sidebar_template
    assert 'can_create_child_folder' in sidebar_template


def test_preset_sidebar_template_includes_category_tree_section():
    sidebar_template = read_project_file('templates/components/sidebar.html')

    assert "currentMode === 'presets'" in sidebar_template
    assert '预设分类' in sidebar_template
    assert 'presetFolderTree' in sidebar_template
    assert 'setPresetCategory' in sidebar_template
    assert 'getPresetCategoryCount' in sidebar_template
    assert 'folder_capabilities' in sidebar_template or 'getFolderCapabilities' in sidebar_template


def test_worldinfo_grid_template_exposes_category_metadata_and_mode_hints():
    wi_grid_template = read_project_file('templates/components/grid_wi.html')

    assert 'display_category' not in wi_grid_template
    assert 'category_mode' not in wi_grid_template
    assert 'showWorldInfoCategoryActions(item, $event)' not in wi_grid_template
    assert '移动到分类' not in wi_grid_template
    assert '设置管理器分类' not in wi_grid_template
    assert '恢复跟随角色卡' not in wi_grid_template
    assert '(item.source_type || item.type) === \'embedded\'' not in wi_grid_template
    assert 'selectedIds.includes(item.id)' in wi_grid_template
    assert 'toggleSelection(item)' in wi_grid_template
    assert 'handleWorldInfoClick($event, item)' in wi_grid_template
    assert '@click.ctrl.stop' not in wi_grid_template
    assert 'draggable="true"' in wi_grid_template
    assert 'jumpToCardFromWi(getWorldInfoOwnerId(item))' in wi_grid_template
    assert '如需调整分类，请移动所属角色卡' not in wi_grid_template
    assert '分类：' not in wi_grid_template
    assert '跟随角色卡' not in wi_grid_template
    assert '已覆盖管理器分类' not in wi_grid_template
    assert '内嵌世界书跟随角色卡分类' not in wi_grid_template
    assert 'isEmbeddedWorldInfo(item)' not in wi_grid_template
    assert 'locateWorldInfoOwnerCard(item)' not in wi_grid_template
    assert 'wi-book-classification' not in wi_grid_template


def test_worldinfo_grid_template_supports_flip_note_preview_and_note_actions():
    wi_grid_template = read_project_file('templates/components/grid_wi.html')

    assert 'card-flip-inner' in wi_grid_template
    assert ':key="getWorldInfoRenderKey(item)"' in wi_grid_template
    assert 'wi-item-flip-corner' in wi_grid_template
    assert 'local-note-preview wi-back-note' in wi_grid_template
    assert 'toggleWorldInfoFace(item.id)' in wi_grid_template
    assert 'worldInfoHasLocalNote(item)' in wi_grid_template
    assert 'openWorldInfoLocalNote(item)' in wi_grid_template


def test_worldinfo_grid_template_uses_info_card_front_layout():
    wi_grid_template = read_project_file('templates/components/grid_wi.html')

    assert 'wi-card-header' in wi_grid_template
    assert 'wi-card-primary' in wi_grid_template
    assert 'wi-card-owner-row' in wi_grid_template
    assert 'wi-card-tag-placeholder' in wi_grid_template
    assert '标签待接入' in wi_grid_template or 'getWorldInfoTagPlaceholder(item)' in wi_grid_template


def test_worldinfo_grid_template_uses_back_note_reading_layout():
    wi_grid_template = read_project_file('templates/components/grid_wi.html')

    assert 'wi-card-back-note-wrap' in wi_grid_template
    assert 'wi-card-back-meta' in wi_grid_template
    assert 'card-bottom-toolbar wi-card-bottom-toolbar' not in wi_grid_template


def test_worldinfo_detail_template_includes_local_note_editor_actions():
    wi_detail_template = read_project_file('templates/modals/detail_wi_popup.html')

    assert '本地备注' in wi_detail_template
    assert 'saveActiveWorldInfoNote()' in wi_detail_template
    assert 'clearActiveWorldInfoNote()' in wi_detail_template
    assert 'openActiveWorldInfoNotePreview()' in wi_detail_template
    assert 'activeWiDetail?.type === \'embedded\'' in wi_detail_template or 'activeWiDetail?.type !== \'embedded\'' in wi_detail_template


def test_worldinfo_editor_template_includes_local_note_panel():
    wi_editor_template = read_project_file('templates/modals/detail_wi_fullscreen.html')

    assert '本地备注 (Local Note)' in wi_editor_template
    assert 'saveEditingWorldInfoNote()' in wi_editor_template
    assert "openLargeEditor('ui_summary','本地备注', false, 0, editingData)" in wi_editor_template
    assert 'openEditingWorldInfoNotePreview()' in wi_editor_template


def test_preset_grid_template_exposes_category_metadata_and_mode_hints():
    preset_grid_template = read_project_file('templates/components/grid_presets.html')

    assert 'display_category' not in preset_grid_template
    assert 'category_mode' not in preset_grid_template
    assert 'showPresetCategoryActions(item, $event)' not in preset_grid_template
    assert '移动到分类' not in preset_grid_template
    assert '设置管理器分类' not in preset_grid_template
    assert '恢复跟随角色卡' not in preset_grid_template
    assert '分类：' not in preset_grid_template
    assert 'class="text-[10px] text-[var(--text-dim)] space-y-1 mb-3"' not in preset_grid_template
    assert 'selectedIds.includes(item.id)' in preset_grid_template
    assert 'toggleSelection(item)' in preset_grid_template
    assert 'handlePresetClick($event, item)' in preset_grid_template
    assert '@click.ctrl.stop' not in preset_grid_template
    assert 'draggable="true"' in preset_grid_template


def test_state_js_tracks_mode_specific_category_state_for_worldinfo_and_presets():
    state_source = read_project_file('static/js/state.js')

    assert 'wiFilterCategory' in state_source
    assert 'wiAllFolders' in state_source
    assert 'wiCategoryCounts' in state_source
    assert 'wiFolderCapabilities' in state_source
    assert 'presetFilterCategory' in state_source
    assert 'presetAllFolders' in state_source
    assert 'presetCategoryCounts' in state_source
    assert 'presetFolderCapabilities' in state_source


def test_sidebar_js_handles_mode_specific_category_trees_and_capability_gating():
    sidebar_source = read_project_file('static/js/components/sidebar.js')

    assert 'wiFolderTree' in sidebar_source
    assert 'presetFolderTree' in sidebar_source
    assert 'setWiCategory' in sidebar_source
    assert 'setPresetCategory' in sidebar_source
    assert 'getFolderCapabilities(path, mode = this.currentMode)' in sidebar_source
    assert 'reset invalid category selection to root' not in sidebar_source
    assert 'this.$watch(\'$store.global.wiAllFolders\'' in sidebar_source
    assert 'this.$watch(\'$store.global.presetAllFolders\'' in sidebar_source


def test_worldinfo_grid_js_uses_category_metadata_and_explicit_upload_fallback_contract():
    wi_grid_source = read_project_file('static/js/components/wiGrid.js')

    assert 'category: this.wiFilterCategory' in wi_grid_source
    assert 'all_folders' in wi_grid_source
    assert 'category_counts' in wi_grid_source
    assert 'folder_capabilities' in wi_grid_source
    assert 'target_category' in wi_grid_source
    assert 'requires_global_fallback_confirmation' in wi_grid_source
    assert 'allow_global_fallback' in wi_grid_source
    assert 'toggleSelection(item)' in wi_grid_source
    assert 'handleWorldInfoClick(e, item)' in wi_grid_source
    assert 'if (e.ctrlKey || e.metaKey)' in wi_grid_source
    assert 'if (e.shiftKey && this.lastSelectedId)' in wi_grid_source
    assert 'dragStart(e, item)' in wi_grid_source
    assert 'canSelectWorldInfoItem(item)' in wi_grid_source
    assert 'canDeleteWorldInfoSelection()' in wi_grid_source
    assert 'canMoveWorldInfoSelection()' in wi_grid_source
    assert 'deleteSelectedWorldInfo()' in wi_grid_source
    assert 'if (!this.canSelectWorldInfoItem(item)) return;' in wi_grid_source
    assert "this.wiFilterType === 'global' || this.wiFilterType === 'all'" in wi_grid_source
    assert 'owner_card_id' in wi_grid_source
    assert 'owner_card_name' in wi_grid_source
    assert 'source_type' in wi_grid_source
    assert 'movableItems.length !== selectedItems.length' not in wi_grid_source
    assert 'ids = [item.id]' not in wi_grid_source
    assert 'if (!this.canMoveWorldInfoSelection()) {' in wi_grid_source


def test_worldinfo_grid_js_syncs_local_note_updates_without_waiting_for_refetch():
    wi_grid_source = read_project_file('static/js/components/wiGrid.js')

    assert 'wi-note-updated' in wi_grid_source
    assert 'getWorldInfoRenderKey(item)' in wi_grid_source
    assert 'item.id !== detail.id' in wi_grid_source or 'item.id === detail.id' in wi_grid_source
    assert "item.ui_summary = detail.ui_summary || ''" in wi_grid_source
    assert 'this.wiList = currentItems;' in wi_grid_source


def test_worldinfo_grid_js_exposes_redesign_display_helpers():
    wi_grid_source = read_project_file('static/js/components/wiGrid.js')

    assert 'getWorldInfoRenderKey(item)' in wi_grid_source
    assert 'getWorldInfoTagPlaceholder(' in wi_grid_source
    assert 'getWorldInfoNoteState(' in wi_grid_source


def test_preset_grid_js_uses_category_metadata_and_explicit_upload_fallback_contract():
    preset_grid_source = read_project_file('static/js/components/presetGrid.js')

    assert 'category=' in preset_grid_source
    assert 'all_folders' in preset_grid_source
    assert 'category_counts' in preset_grid_source
    assert 'folder_capabilities' in preset_grid_source
    assert 'target_category' in preset_grid_source
    assert 'requires_global_fallback_confirmation' in preset_grid_source
    assert 'allow_global_fallback' in preset_grid_source
    assert 'toggleSelection(item)' in preset_grid_source
    assert 'handlePresetClick(e, item)' in preset_grid_source
    assert 'if (e.ctrlKey || e.metaKey)' in preset_grid_source
    assert 'if (e.shiftKey && this.lastSelectedId)' in preset_grid_source
    assert 'dragStart(e, item)' in preset_grid_source
    assert 'canSelectPresetItem(item)' in preset_grid_source
    assert 'canDeletePresetSelection()' in preset_grid_source
    assert 'canMovePresetSelection()' in preset_grid_source
    assert 'deleteSelectedPresets()' in preset_grid_source
    assert 'moveSelectedPresets(targetCategory = this.filterCategory || \'\')' in preset_grid_source
    assert 'selectedPresetItems()' in preset_grid_source
    assert 'isPresetMovable(item)' in preset_grid_source
    assert 'selectedItems.length === 0 || !selectedItems.every(currentItem => this.isPresetMovable(currentItem))' in preset_grid_source
    assert '当前选中的预设包含资源绑定项，不能移动分类' in preset_grid_source
    assert 'ids = Array.of(item.id);' not in preset_grid_source
    drag_start_block = extract_js_function_block(preset_grid_source, 'dragStart(e, item)')
    assert drag_start_block.index('selectedItems.length === 0 || !selectedItems.every(currentItem => this.isPresetMovable(currentItem))') < drag_start_block.index('this.selectedIds = ids;')
    assert "this.filterType === 'global' || this.filterType === 'all'" in preset_grid_source
    assert 'owner_card_id' in preset_grid_source
    assert 'owner_card_name' in preset_grid_source
    assert 'source_type' in preset_grid_source
    assert 'showPresetCategoryActions' not in preset_grid_source
    assert 'movePresetToCategory(item)' not in preset_grid_source
    assert 'resetPresetCategory(item)' not in preset_grid_source


def test_preset_grid_template_uses_selection_without_card_level_category_actions():
    preset_template = read_project_file('templates/components/grid_presets.html')

    assert 'toggleSelection(item)' in preset_template
    assert 'handlePresetClick($event, item)' in preset_template
    assert 'dragStart($event, item)' in preset_template
    assert 'draggable="true"' in preset_template
    assert 'data-preset-id' in preset_template
    assert 'showPresetCategoryActions' not in preset_template
    assert '移动到分类' not in preset_template
    assert '跟随角色卡' not in preset_template
    assert '已覆盖管理器分类' not in preset_template
    assert '<span>分类：</span>' not in preset_template
    assert 'locatePresetOwnerCard(item)' in preset_template
    assert 'class="text-[10px] text-[var(--text-dim)] space-y-1 mb-3"' not in preset_template


def test_sidebar_template_uses_scrollable_worldinfo_and_preset_category_sections():
    sidebar_template = read_project_file('templates/components/sidebar.html')
    sidebar_source = read_project_file('static/js/components/sidebar.js')
    layout_css = read_project_file('static/css/modules/layout.css')

    assert 'worldinfo-sidebar-tree' in sidebar_template
    assert 'preset-sidebar-tree' in sidebar_template
    assert "currentMode === 'worldinfo' && visibleSidebar" in sidebar_template
    assert "currentMode === 'presets' && visibleSidebar" in sidebar_template
    assert "class=\"p-4 space-y-2 flex-1 min-h-0 flex flex-col\"" in sidebar_template
    assert '@dragover.prevent="handleDragOverRoot($event)"' in sidebar_template
    assert '@drop.prevent="handleDropOnRoot($event)"' in sidebar_template
    assert '@dragover.prevent="presetRootDragOver($event)"' in sidebar_template
    assert '@drop.prevent="presetRootDrop($event)"' in sidebar_template
    assert "folderDragOver($event, { ...folder, mode: 'presets' })" in sidebar_template
    assert "folderDrop($event, { ...folder, mode: 'presets' })" in sidebar_template
    assert 'canMovePresetSelection()' in sidebar_source
    assert 'presetRootDrop(e)' in sidebar_source
    assert 'presetRootDragOver(e)' in sidebar_source
    assert '.worldinfo-sidebar-tree,' in layout_css
    assert '.preset-sidebar-tree {' in layout_css
    assert 'min-height: 0;' in layout_css
    assert 'overflow-y: auto;' in layout_css


def test_worldinfo_css_exposes_hover_visible_selection_overlay():
    wi_css = read_project_file('static/css/modules/view-wi.css')

    assert '.wi-grid-card:hover .card-select-overlay' in wi_css


def test_header_selection_bar_switches_to_worldinfo_specific_actions():
    header_template = read_project_file('templates/components/header.html')
    header_source = read_project_file('static/js/components/header.js')

    assert "currentMode === 'worldinfo'" in header_template
    assert 'deleteSelectedWorldInfo()' in header_template
    assert 'moveSelectedWorldInfo()' in header_template
    assert 'canMoveWorldInfoSelection()' in header_template
    assert 'openBatchTagModal()' in header_template
    assert 'executeRuleSet(rs.id)' in header_template
    assert 'deleteSelectedWorldInfo()' in header_source
    assert 'canDeleteWorldInfoSelection()' in header_source
    assert 'canMoveWorldInfoSelection()' in header_source
    assert 'selectedWorldInfoItems()' in header_source


def test_header_selection_bar_switches_to_preset_specific_actions():
    header_template = read_project_file('templates/components/header.html')
    header_source = read_project_file('static/js/components/header.js')

    assert "currentMode === 'presets'" in header_template
    assert 'deleteSelectedPresets()' in header_template
    assert 'moveSelectedPresets()' in header_template
    assert 'canMovePresetSelection()' in header_template
    assert "x-show=\"selectedIds.length > 0 && currentMode === 'cards'\"" in header_template
    assert 'deleteSelectedPresets()' in header_source
    assert 'canDeletePresetSelection()' in header_source
    assert 'canMovePresetSelection()' in header_source
    assert 'selectedPresetItems()' in header_source


def test_worldinfo_preset_context_menu_delete_copy_is_not_card_specific():
    context_menu_template = read_project_file('templates/components/context_menu.html')
    context_menu_source = read_project_file('static/js/components/contextMenu.js')

    assert 'deleteFolderConfirm.mode' in context_menu_template or 'deleteFolderConfirm.mode' in context_menu_source
    assert 'deleteFolderItemLabel' in context_menu_template
    assert "? '个项目'" in context_menu_source
    assert ": '张卡片'" in context_menu_source


def test_folder_operations_filters_parent_choices_to_capability_allowed_targets():
    folder_operations_source = read_project_file('static/js/components/folderOperations.js')
    folder_modal_template = read_project_file('templates/modals/folder_operations.html')

    assert 'creatableFolderSelectList' in folder_operations_source
    assert 'can_create_child_folder' in folder_operations_source
    assert 'x-for="folder in creatableFolderSelectList"' in folder_modal_template


def test_card_sidebar_mobile_css_pins_collapsed_tag_strip_to_sidebar_bottom():
    layout_css = read_project_file('static/css/modules/layout.css')
    mobile_layout_css = extract_media_block(layout_css, '@media (max-width: 768px)')

    assert '.sidebar-mobile .card-sidebar-shell {' in mobile_layout_css
    assert 'overflow: visible;' in mobile_layout_css
    assert '.sidebar-mobile .card-sidebar-tags {' in mobile_layout_css
    assert 'position: sticky;' in mobile_layout_css
    assert 'bottom: 0;' in mobile_layout_css
    assert '.sidebar-mobile .card-sidebar-tags.is-collapsed {' in mobile_layout_css
    assert 'z-index: 2;' in mobile_layout_css


def test_mobile_sidebar_css_uses_container_height_instead_of_fixed_dynamic_viewport_height():
    layout_css = read_project_file('static/css/modules/layout.css')
    sidebar_mobile_block = extract_exact_css_block(layout_css, '.sidebar-mobile')

    assert 'height: 100%;' in sidebar_mobile_block
    assert 'max-height: 100%;' in sidebar_mobile_block
    assert 'height: 100dvh;' not in sidebar_mobile_block
    assert 'max-height: 100dvh;' not in sidebar_mobile_block


def test_card_pagination_template_uses_mobile_short_labels_and_hides_flip_count():
    cards_template = read_project_file('templates/components/grid_cards.html')

    assert 'class="card-pagination-page-indicator"' in cards_template
    assert 'class="btn-secondary card-page-nav-btn"' in cards_template
    assert "x-show=\"$store.global.deviceType === 'mobile' && !bulkBackMode\">翻面</span>" in cards_template
    assert "x-show=\"$store.global.deviceType === 'mobile' && bulkBackMode\">正面</span>" in cards_template
    assert "x-show=\"$store.global.deviceType !== 'mobile'\" class=\"card-flip-count\"" in cards_template


def test_card_pagination_mobile_css_compacts_footer_into_single_row():
    cards_css = read_project_file('static/css/modules/view-cards.css')
    mobile_cards_css = extract_media_block(cards_css, '@media (max-width: 768px)')

    assert 'flex-direction: row;' in mobile_cards_css
    assert 'justify-content: space-between;' in mobile_cards_css
    assert 'flex-wrap: nowrap;' in mobile_cards_css
    assert '.card-flip-toolbar {' in mobile_cards_css
    assert 'width: auto;' in mobile_cards_css
    assert 'background: transparent;' in mobile_cards_css
    assert 'border: none;' in mobile_cards_css
    assert '.card-pagination-page-cluster {' in mobile_cards_css
    assert 'width: auto;' in mobile_cards_css
    assert '.card-page-nav-btn {' in mobile_cards_css
    assert '.card-pagination-page-indicator {' in mobile_cards_css
