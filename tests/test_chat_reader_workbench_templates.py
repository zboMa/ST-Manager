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


def extract_chat_reader_shell(template_source):
    shell_start = template_source.index('<div class="chat-reader-modal chat-reader-modal--fullscreen" role="dialog" aria-modal="true" aria-label="聊天阅读器">')
    settings_overlay_start = template_source.index('<div x-show="readerViewSettingsOpen"')
    return template_source[shell_start:settings_overlay_start]


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


def test_chat_reader_template_contains_workbench_regions():
    reader_template = read_project_file('templates/modals/detail_chat_reader.html')
    shell = extract_chat_reader_shell(reader_template)

    shell_pattern = re.compile(
        r'<div class="chat-reader-header">.*?'
        r'<div class="chat-reader-body" :style="readerBodyGridStyle">.*?'
        r'<aside x-show="readerShowLeftPanel" class="chat-reader-left custom-scrollbar">.*?'
        r'<main class="chat-reader-center custom-scrollbar" @scroll.passive="handleReaderScroll\(\)">.*?'
        r'<aside x-show="readerShowRightPanel" class="chat-reader-right custom-scrollbar">',
        re.DOTALL,
    )

    assert shell_pattern.search(shell)
    assert shell.count('<aside ') == 2
    assert shell.index('class="chat-reader-header"') < shell.index('class="chat-reader-body"')
    assert '<div class="chat-reader-body" :style="readerBodyGridStyle">\n            <aside x-show="readerShowLeftPanel" class="chat-reader-left custom-scrollbar">' in shell
    assert '\n            </aside>\n\n            <main class="chat-reader-center custom-scrollbar" @scroll.passive="handleReaderScroll()">' in shell
    assert '\n            </main>\n\n            <aside x-show="readerShowRightPanel" class="chat-reader-right custom-scrollbar">' in shell


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
    assert 'this.reconcileReaderPanelsForDeviceType(deviceType);' in chat_grid_source
    assert "if (deviceType === 'mobile')" in chat_grid_source
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
