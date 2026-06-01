from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_task_019_frontend_edits_similar_questions_and_faq_index_modes():
    types = read("frontend/src/types/api.ts")
    store = read("frontend/src/stores/knowledgeBase.ts")
    faq_view = read("frontend/src/views/FAQView.vue")
    detail_view = read("frontend/src/views/KnowledgeBaseDetailView.vue")
    styles = read("frontend/src/styles/app.css")

    assert "FAQConfig" in types
    assert "similar_questions" in types
    assert "faq_config" in types
    assert "similarQuestionsText" in faq_view
    assert "parseSimilarQuestions" in faq_view
    assert "相似问法" in faq_view
    assert "一行一个，或使用 ## 分隔" in faq_view
    assert "similar-question-list" in faq_view
    assert "matched_question" in faq_view
    assert "命中问法" in faq_view
    assert "similar_questions" in store
    assert "faqIndexMode" in detail_view
    assert "faqQuestionIndexMode" in detail_view
    assert "FAQ index mode" in detail_view
    assert "question_only" in detail_view
    assert "question_answer" in detail_view
    assert "combined" in detail_view
    assert "separate" in detail_view
    assert "faq-config-panel" in styles
    assert "similar-question-list" in styles
