from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def test_chat_reader_workbench_removes_runtime_inspector_references():
    header_template = read_project_file('templates/components/header.html')
    index_template = read_project_file('templates/index.html')
    app_source = read_project_file('static/js/app.js')
    header_source = read_project_file('static/js/components/header.js')

    assert 'openRuntimeInspector' not in header_template
    assert '运行时检查器' not in header_template
    assert 'runtime_inspector.html' not in index_template
    assert "import runtimeInspector from './components/runtimeInspector.js';" not in app_source
    assert "Alpine.data('runtimeInspector', runtimeInspector);" not in app_source
    assert 'openRuntimeInspector' not in header_source
    assert 'open-runtime-inspector' not in header_source
