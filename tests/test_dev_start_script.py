import re
from pathlib import Path


def _powershell_function_body(content: str, name: str) -> str:
    match = re.search(rf"function {name} \{{(?P<body>.*?)\n\}}", content, re.DOTALL)
    assert match, f"{name} not found"
    return match.group("body")


def test_windows_dev_start_script_documents_full_stack_commands():
    script = Path("scripts/start-dev.ps1")
    assert script.exists()

    content = script.read_text(encoding="utf-8")
    assert "docker compose up -d --build" in content
    assert "Invoke-CheckedNative" in content
    assert "$LASTEXITCODE" in content
    assert 'Invoke-CheckedNative -FilePath "docker" -ArgumentList @("compose", "up", "-d", "--build")' in content
    assert "uvicorn app.main:app --reload" not in content
    assert "celery -A app.workers.celery_app:celery_app worker --loglevel=info --pool=solo" not in content
    assert "alembic upgrade head" not in content
    assert "npm --prefix frontend run dev" in content
    assert "scripts/stop-dev.ps1" in content


def test_double_click_batch_wrappers_call_powershell_scripts():
    start = Path("start-dev.bat")
    stop = Path("stop-dev.bat")
    restart_frontend = Path("restart-frontend.bat")

    assert start.exists()
    assert stop.exists()
    assert restart_frontend.exists()
    assert "scripts\\start-dev.ps1" in start.read_text(encoding="utf-8")
    assert "scripts\\stop-dev.ps1" in stop.read_text(encoding="utf-8")
    assert "scripts\\restart-frontend.ps1" in restart_frontend.read_text(encoding="utf-8")


def test_windows_dev_stop_script_stops_compose_backend_stack():
    script = Path("scripts/stop-dev.ps1")
    assert script.exists()

    content = script.read_text(encoding="utf-8")
    assert "docker compose stop api worker postgres redis qdrant" in content
    assert 'Invoke-CheckedNative -FilePath "docker" -ArgumentList @(' in content
    assert '"compose", "stop", "api", "worker", "postgres", "redis", "qdrant"' in content


def test_windows_dev_scripts_stop_local_knowmate_api_and_worker_by_module_name():
    for script in [Path("scripts/start-dev.ps1"), Path("scripts/stop-dev.ps1")]:
        content = script.read_text(encoding="utf-8")
        body = _powershell_function_body(content, "Stop-KnowmatePythonProcessPattern")
        assert "Stop-KnowmatePythonProcessPattern" in content
        assert "app\\.workers\\.celery_app:celery_app|celery_app" in content
        assert "uvicorn.*app\\.main:app|app\\.main:app.*uvicorn" in content
        assert "Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue" in body
        assert "taskkill" not in body


def test_windows_scripts_use_crlf_and_ascii_safe_content():
    for script in [
        Path("start-dev.bat"),
        Path("stop-dev.bat"),
        Path("restart-frontend.bat"),
        Path("scripts/start-dev.ps1"),
        Path("scripts/stop-dev.ps1"),
        Path("scripts/restart-frontend.ps1"),
    ]:
        data = script.read_bytes()
        assert b"\r\n" in data
        assert b"\n" not in data.replace(b"\r\n", b"")
        data.decode("ascii")


def test_alembic_revision_ids_fit_default_version_table_length():
    revision_pattern = re.compile(r'^revision: str = "([^"]+)"', re.MULTILINE)
    for script in Path("alembic/versions").glob("*.py"):
        match = revision_pattern.search(script.read_text(encoding="utf-8"))
        assert match, f"{script} does not define revision"
        revision = match.group(1)
        assert len(revision) <= 32, f"{script.name} revision is too long for alembic_version.version_num"
