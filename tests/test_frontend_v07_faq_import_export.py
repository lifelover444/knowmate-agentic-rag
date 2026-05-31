from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_task_006_faq_import_export_and_search_panel_wiring():
    store = read("frontend/src/stores/knowledgeBase.ts")
    view = read("frontend/src/views/FAQView.vue")
    types = read("frontend/src/types/api.ts")
    api = read("frontend/src/utils/api.ts")

    assert "downloadRequest" in api
    assert "FAQImportResult" in types
    assert "FAQSearchTestResult" in types
    assert "importFaqs" in store
    assert "/knowledge-bases/${kbId}/faqs/import" in store
    assert "exportFaqs" in store
    assert "/knowledge-bases/${kbId}/faqs/export" in store
    assert "searchFaqKnowledge" in store
    assert 'mode: "hybrid"' in store
    assert "FAQ 导入" in view
    assert "append" in view
    assert "replace" in view
    assert "导入结果" in view
    assert "失败行" in view
    assert "导出 CSV" in view
    assert "导出 XLSX" in view
    assert "FAQ 检索测试" in view
    assert "kbStore.faqSearchHits" in view
