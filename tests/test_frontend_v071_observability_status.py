from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_loads_runtime_status_and_shows_stage_trace():
    app = frontend_source()

    assert "RuntimeStatus" in app
    assert "loadRuntimeStatus" in app
    assert "/runtime-status" in app
    assert "runtimeStatus" in app
    assert "parser_engine_status" in app
    assert "storage-provider-status" in app
    assert "系统状态" in app

    assert "traceStages" in app
    assert "trace-stage-list" in app
    assert "rewrite" in app
    assert "search" in app
    assert "rerank" in app
    assert "answer" in app
