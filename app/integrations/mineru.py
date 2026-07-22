import json
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

import httpx


class MinerUError(RuntimeError):
    pass


@dataclass(frozen=True)
class MinerUConfig:
    base_url: str = "https://mineru.net/api/v4"
    api_key: str = ""
    model_version: str = "vlm"
    language: str = "ch"
    enable_table: bool = True
    enable_formula: bool = True
    is_ocr: bool = False
    poll_interval_seconds: float = 3
    poll_timeout_seconds: float = 600


@dataclass(frozen=True)
class MinerUParseResult:
    markdown: str
    metadata: dict[str, Any] = field(default_factory=dict)


class MinerUClient:
    def __init__(
        self,
        config: MinerUConfig,
        http_client: httpx.Client | None = None,
        cancel_check: Callable[[], None] | None = None,
    ) -> None:
        self.config = config
        self.http = http_client or httpx.Client(timeout=60)
        self.cancel_check = cancel_check

    def parse_file(self, path: Path) -> MinerUParseResult:
        if not self.config.api_key:
            raise MinerUError("MinerU API Key 未配置")
        self._check_cancelled()
        batch_id, upload_url, submit_trace_id = self._create_upload_task(path)
        self._upload_file(path, upload_url)
        result = self._poll_result(batch_id, path.name)
        markdown, archive_metadata = self._download_and_read_markdown(result["full_zip_url"])
        metadata = {
            "parser": "mineru",
            "mineru_batch_id": batch_id,
            "mineru_state": result.get("state"),
            "mineru_trace_id": result.get("trace_id") or submit_trace_id,
            "full_zip_url": result.get("full_zip_url"),
            "model_version": self.config.model_version,
            **archive_metadata,
        }
        return MinerUParseResult(markdown=markdown.strip(), metadata=metadata)

    def _create_upload_task(self, path: Path) -> tuple[str, str, str | None]:
        payload: dict[str, Any] = {
            "files": [{"name": path.name, "data_id": _safe_data_id(path)}],
            "model_version": self.config.model_version,
            "language": self.config.language,
            "enable_table": self.config.enable_table,
            "enable_formula": self.config.enable_formula,
        }
        payload["files"][0]["is_ocr"] = self.config.is_ocr
        response = self._request("POST", f"{self._base_url}/file-urls/batch", json=payload)
        data = response.get("data") or {}
        batch_id = str(data.get("batch_id") or "")
        file_urls = data.get("file_urls") or []
        if not batch_id or not file_urls:
            raise MinerUError("MinerU 创建解析任务失败：响应缺少 batch_id 或上传地址")
        return batch_id, str(file_urls[0]), response.get("trace_id")

    def _upload_file(self, path: Path, upload_url: str) -> None:
        with path.open("rb") as file:
            response = self.http.put(upload_url, content=file)
        if response.status_code not in {200, 201}:
            raise MinerUError(f"MinerU 文件上传失败：HTTP {response.status_code}")

    def _poll_result(self, batch_id: str, file_name: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.config.poll_timeout_seconds
        last_state = "unknown"
        while time.monotonic() <= deadline:
            self._check_cancelled()
            response = self._request("GET", f"{self._base_url}/extract-results/batch/{batch_id}")
            data = response.get("data") or {}
            item = _select_extract_result(data.get("extract_result") or [], file_name)
            if item:
                item["trace_id"] = response.get("trace_id")
                state = str(item.get("state") or "")
                last_state = state or last_state
                if state == "done":
                    if not item.get("full_zip_url"):
                        raise MinerUError("MinerU 解析完成但未返回结果压缩包")
                    return item
                if state == "failed":
                    err_msg = item.get("err_msg") or "未知错误"
                    raise MinerUError(f"MinerU 解析失败：{err_msg}")
            if self.config.poll_interval_seconds > 0:
                time.sleep(self.config.poll_interval_seconds)
        raise MinerUError(f"MinerU 解析超时：batch_id={batch_id}，最后状态={last_state}")

    def _check_cancelled(self) -> None:
        if self.cancel_check is not None:
            self.cancel_check()

    def _download_and_read_markdown(self, full_zip_url: str) -> tuple[str, dict[str, Any]]:
        response = self.http.get(full_zip_url)
        if response.status_code != 200:
            raise MinerUError(f"MinerU 结果下载失败：HTTP {response.status_code}")
        try:
            with ZipFile(BytesIO(response.content)) as archive:
                markdown_name = next((name for name in archive.namelist() if name.endswith("full.md")), None)
                if markdown_name is None:
                    raise MinerUError("MinerU 结果包缺少 full.md")
                markdown = archive.read(markdown_name).decode("utf-8", errors="replace")
                metadata = _archive_metadata(archive)
                return markdown, metadata
        except MinerUError:
            raise
        except BadZipFile as exc:
            raise MinerUError("MinerU 结果包不是有效 zip 文件") from exc

    def _request(self, method: str, url: str, **kwargs) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        response = self.http.request(method, url, headers=headers, **kwargs)
        if response.status_code >= 400:
            raise MinerUError(f"MinerU 请求失败：HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise MinerUError("MinerU 响应不是有效 JSON") from exc
        if payload.get("code") != 0:
            code = payload.get("code")
            msg = payload.get("msg") or "未知错误"
            raise MinerUError(f"MinerU 请求失败：{msg}（{code}）")
        return payload

    @property
    def _base_url(self) -> str:
        return self.config.base_url.rstrip("/")


def _select_extract_result(items: list[dict[str, Any]], file_name: str) -> dict[str, Any] | None:
    if not items:
        return None
    for item in items:
        if item.get("file_name") == file_name:
            return item
    return items[0]


def _safe_data_id(path: Path) -> str:
    allowed = []
    for char in path.stem:
        is_ascii_alphanumeric = char.isascii() and char.isalnum()
        allowed.append(char if is_ascii_alphanumeric or char in {"_", "-", "."} else "_")
    value = "".join(allowed).strip("._-") or "document"
    return value[:128]


def _archive_metadata(archive: ZipFile) -> dict[str, Any]:
    names = archive.namelist()
    metadata: dict[str, Any] = {"mineru_output_files": names}
    content_name = next((name for name in names if name.endswith("_content_list.json")), None)
    if content_name:
        try:
            content_list = json.loads(archive.read(content_name).decode("utf-8", errors="replace"))
            if isinstance(content_list, list):
                counter = Counter(str(item.get("type") or "unknown") for item in content_list if isinstance(item, dict))
                metadata["content_list_summary"] = dict(counter)
        except (ValueError, KeyError):
            metadata["content_list_summary"] = {}
    return metadata
