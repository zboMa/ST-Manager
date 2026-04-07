from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def test_worldinfo_editors_store_and_send_source_revision():
    wi_editor = read_project_file('static/js/components/wiEditor.js')
    wi_popup = read_project_file('static/js/components/wiDetailPopup.js')
    wi_api = read_project_file('static/js/api/wi.js')

    assert 'this.editingWiFile.source_revision = res.source_revision || "";' in wi_editor
    assert 'source_revision: this.editingWiFile?.source_revision || "",' in wi_editor
    assert 'source_revision: this.activeWiDetail?.source_revision || "",' in wi_popup
    assert 'export async function searchWorldInfoDetail(payload) {' in wi_api
    assert 'const res = await searchWorldInfoDetail({' in wi_popup
    assert 'query: this.searchTerm,' in wi_popup
    assert 'const targetId = item.id;' in wi_editor
    assert 'if (!this.editingWiFile || this.editingWiFile.id !== targetId) return;' in wi_editor
    assert 'const openRequestToken = ++this.openWorldInfoEditorRequestToken;' in wi_editor
    assert 'if (openRequestToken !== this.openWorldInfoEditorRequestToken) return;' in wi_editor
    assert 'if (targetId && this.activeWiDetail.id !== targetId) return;' in wi_popup
    assert 'window.dispatchEvent(new CustomEvent("refresh-wi-list"));' in wi_editor
    assert 'const loadToken = ++this.loadRequestToken;' in wi_popup
    assert 'if (loadToken !== this.loadRequestToken) return;' in wi_popup
    assert 'this.activeWiDetail = {' in wi_popup
    assert 'source_revision:' in wi_popup
    assert 'res.card?.source_revision ||' in wi_popup
    assert 'const targetId = item.id;' in wi_editor
    assert 'this.openWorldInfoFileRequestToken += 1;' in wi_editor
    assert '.catch((e) => {' in wi_editor
    assert 'alert("加载失败: " + e);' in wi_editor
