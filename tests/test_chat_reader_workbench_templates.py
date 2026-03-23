from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def extract_css_block(css_source, selector):
    selector_start = css_source.index(selector)
    block_start = css_source.index('{', selector_start)
    block_end = css_source.index('}', block_start)
    return css_source[block_start + 1:block_end]


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
