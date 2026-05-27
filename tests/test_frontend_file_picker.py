from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    )


def test_file_picker_uses_native_input_as_full_click_target():
    app = frontend_source()
    css = (ROOT / "frontend" / "src" / "styles" / "app.css").read_text(encoding="utf-8")

    assert 'ref="fileInput"' not in app
    assert "@click=\"openFilePicker\"" not in app
    assert 'class="file-picker"' in app
    assert 'data-testid="file-input"' in app

    native_block_start = css.index(".native-file-input")
    native_block = css[native_block_start : css.index("}", native_block_start)]
    assert "inset: 0" in native_block
    assert "width: 100%" in native_block
    assert "height: 100%" in native_block
    assert "opacity: 0" in native_block
    assert "cursor: pointer" in native_block
    assert "clip:" not in native_block
    assert "clip-path:" not in native_block
