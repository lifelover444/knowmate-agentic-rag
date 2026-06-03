from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_faq_batch_field_update_frontend_wiring():
    store = read("frontend/src/stores/knowledgeBase.ts")
    view = read("frontend/src/views/FAQView.vue")
    types = read("frontend/src/types/api.ts")

    assert "FAQFieldBatchUpdateRequest" in types
    assert "FAQFieldBatchUpdateResponse" in types
    assert "is_recommended" in types
    assert "selectedFaqIds" in store
    assert "batchUpdateFaqFields" in store
    assert "/knowledge-bases/${kbId}/faqs/fields" in store
    assert "selectedFaqIds" in view
    assert "批量启用" in view
    assert "批量停用" in view
    assert "批量标签" in view
    assert "批量推荐" in view
    assert "取消推荐" in view
    assert "batch-update-faq-fields" in view
