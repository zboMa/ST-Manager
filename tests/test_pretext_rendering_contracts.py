from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def test_pretext_vendor_module_exists_and_exports_prepare_and_layout_contracts():
    source = read_project_file('static/js/vendor/pretext/layout.js')

    assert 'export function prepare(' in source
    assert 'export function layout(' in source
    assert 'export function clearCache(' in source
    assert 'export function setLocale(' in source


def test_dom_utils_exposes_pretext_backed_intrinsic_size_helpers():
    source = read_project_file('static/js/utils/dom.js')

    assert 'export function applyPretextIntrinsicSize(' in source
    assert 'export function estimatePretextBlockHeight(' in source
    assert "import('../vendor/pretext/layout.js')" in source
    assert 'let pretextModule = null;' in source
    assert 'module.prepare(' in source
    assert 'module.layout(' in source
    assert 'containIntrinsicSize' in source


def test_chat_reader_uses_pretext_intrinsic_size_hint_before_mounting_message_html():
    source = read_project_file('static/js/components/chatGrid.js')

    assert 'applyPretextIntrinsicSize' in source
    assert "this.applyReaderPretextIntrinsicSize(el, message, variant, html);" in source
    assert 'estimatePretextBlockHeight' in source


def test_large_preview_surfaces_use_pretext_intrinsic_size_hints():
    dom_source = read_project_file('static/js/utils/dom.js')

    assert 'applyPretextIntrinsicSize(el, source,' in dom_source
    assert 'applyPretextIntrinsicSize(host, source,' in dom_source
    assert 'runtimeOwner' in dom_source


def test_preview_entrypoints_continue_using_shared_dom_renderers_that_now_have_pretext_support():
    advanced_editor_template = read_project_file('templates/modals/advanced_editor.html')
    large_editor_template = read_project_file('templates/modals/large_editor.html')
    detail_card_template = read_project_file('templates/modals/detail_card.html')
    html_preview_template = read_project_file('templates/modals/html_preview.html')
    markdown_preview_template = read_project_file('templates/modals/markdown_preview.html')

    assert 'updateMixedPreviewContent($el, regexPreviewMode===\'html\' ? regexTestResult : null' in advanced_editor_template
    assert 'updateMixedPreviewContent($el, markdownPreview ? largeEditorContent : null' in large_editor_template
    assert 'updateMixedPreviewContent($el, showFirstPreview ? editingData.first_mes : null' in detail_card_template
    assert 'updateMixedPreviewContent($el, showLargePreview ? regexTestResult : null' in html_preview_template
    assert 'updateShadowContent($el, showMarkdownModal ? renderMarkdown(markdownModalContent) : null' in markdown_preview_template


def test_chat_reader_css_enables_content_visibility_and_intrinsic_size_placeholder_strategy():
    css_source = read_project_file('static/css/modules/view-chats.css')

    assert '.chat-message-card {' in css_source
    assert 'content-visibility: auto;' in css_source
    assert 'contain-intrinsic-size:' in css_source
    assert '--stm-pretext-block-size:' in css_source

    card_block = css_source.split('.chat-message-card {', 1)[1].split('}', 1)[0]
    content_block = css_source.split('.chat-message-content {', 1)[1].split('}', 1)[0]

    assert 'content-visibility: auto;' not in card_block
    assert 'contain-intrinsic-size:' not in card_block
    assert 'content-visibility: auto;' in content_block
    assert 'contain-intrinsic-size:' in content_block
