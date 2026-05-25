from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_file_picker_uses_native_input_as_full_click_target():
    app = (ROOT / "frontend" / "src" / "App.vue").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")

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
