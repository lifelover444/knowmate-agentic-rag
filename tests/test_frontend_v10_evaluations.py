from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_exposes_ragas_evaluation_workspace():
    app = frontend_source()

    assert "/evaluations" in app
    assert "EvaluationsView" in app
    assert "useEvaluationStore" in app
    assert "/evaluations" in app
    assert "RAGas 评测" in app
    assert "创建评测" in app
    assert "量化结果" in app
    assert "总分" in app
    assert "当前运行" in app
    assert "基线运行" in app
    assert "设为基线" in app
    assert "黄金测试集" in app
    assert "上下文精确率" in app
    assert "上下文召回率" in app
    assert "忠实度" in app
    assert "回答相关性" in app
    assert "事实正确性" in app
    assert "evaluation-heatmap" in app
    assert "expected source" in app
    assert "诊断" in app
    assert "source 明细" in app
    assert "sources" in app
    assert "评测模式" in app
    assert "native_ragas" in app
    assert "semantic_proxy，不是原生 RAGAS" in app
    assert "四项使用原生 RAGAS，事实正确性仍为项目 proxy" in app
    assert "top_k" in app
    assert "rerank" in app
    assert "formatApiError" in app


def test_evaluation_table_does_not_expand_the_result_column():
    view = (ROOT / "frontend" / "src" / "views" / "EvaluationsView.vue").read_text(encoding="utf-8")

    assert ".evaluation-main {\n  display: grid;\n  min-width: 0;" in view
    assert ".evaluation-main > section {\n  min-width: 0;" in view
    assert ".evaluation-heatmap {\n  overflow: hidden;" in view
