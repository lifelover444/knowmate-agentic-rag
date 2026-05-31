from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_frontend_exposes_weknora_like_settings_shell():
    app = frontend_source()
    settings_view = ROOT / "frontend" / "src" / "views" / "SettingsView.vue"

    assert settings_view.exists()
    assert 'path: "/settings"' in app
    assert "设置中心" in app
    assert "settings-shell" in app
    assert "settings-nav" in app

    assert "ModelSettingsView" in app
    assert "VectorStoreSettingsView" in app
    assert "RetrievalSettingsView" in app
    assert "models_runtime" in app
    assert "data_extensions" in app

    assert "parser-engine-status" in app
    assert "Builtin Parser" in app
    assert "Local Parser Registry" in app
    assert "MinerU OCR" in app

    assert "storage-provider-status" in app
    assert "Local Storage" in app
    assert "MinIO" in app
    assert "S3" in app
    assert "OSS" in app
    assert "暂未启用" in app
