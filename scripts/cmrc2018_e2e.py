from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.services.cmrc2018_validation import (
    DEFAULT_SEED,
    CMRCValidationError,
    KnowMateAPI,
    bind_and_import_testset,
    prepare_cmrc2018_dataset,
    run_native_ragas_comparison,
    upload_and_wait_for_corpus,
)

DEFAULT_DATASET_DIR = Path("storage/cmrc2018_validation")


def main() -> None:
    parser = argparse.ArgumentParser(description="CMRC2018 中文 200-context / 20-question 端到端验证工具。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="下载官方 dev 数据并生成纯 context 语料与原始黄金题。")
    prepare.add_argument("--output-dir", type=Path, default=DEFAULT_DATASET_DIR)
    prepare.add_argument("--seed", type=int, default=DEFAULT_SEED)
    prepare.add_argument("--source-file", type=Path, default=None)
    prepare.add_argument("--force", action="store_true")

    upload = subparsers.add_parser("upload", help="上传 manifest 中的 200 个纯 context 文件并等待处理完成。")
    _add_online_arguments(upload)
    upload.add_argument("--no-wait", action="store_true")
    upload.add_argument("--poll-interval", type=float, default=5.0)
    upload.add_argument("--timeout", type=float, default=3600.0)

    bind = subparsers.add_parser("bind", help="按稳定 context ID 找文档/答案 chunk，并导入黄金测试集。")
    _add_online_arguments(bind)
    bind.add_argument("--testset-name", default=None)
    bind.add_argument("--no-import", action="store_true")

    run = subparsers.add_parser("run", help="依次运行 rerank=false/true，并严格验收 native RAGAS。")
    _add_online_arguments(run)
    run.add_argument("--testset-id", default=None)
    run.add_argument("--top-k", type=int, default=5)
    run.add_argument("--output-dir", type=Path, default=None)
    run.add_argument("--poll-interval", type=float, default=5.0)
    run.add_argument("--timeout-per-run", type=float, default=3600.0)

    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_cmrc2018_dataset(
            args.output_dir,
            seed=args.seed,
            source_path=args.source_file,
            force=args.force,
        )
        _print_json(result)
        return

    with KnowMateAPI(args.base_url, timeout=args.api_timeout) as api:
        api.health()
        if args.command == "upload":
            result = upload_and_wait_for_corpus(
                api,
                dataset_dir=args.dataset_dir,
                knowledge_base_id=args.knowledge_base_id,
                wait=not args.no_wait,
                poll_interval=args.poll_interval,
                timeout=args.timeout,
            )
        elif args.command == "bind":
            result = bind_and_import_testset(
                api,
                dataset_dir=args.dataset_dir,
                knowledge_base_id=args.knowledge_base_id,
                testset_name=args.testset_name,
                import_testset=not args.no_import,
            )
        else:
            testset_id = args.testset_id or _saved_testset_id(args.dataset_dir)
            output_dir = args.output_dir or (
                args.dataset_dir / "results" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            )
            result = run_native_ragas_comparison(
                api,
                knowledge_base_id=args.knowledge_base_id,
                testset_id=testset_id,
                output_dir=output_dir,
                top_k=args.top_k,
                poll_interval=args.poll_interval,
                timeout_per_run=args.timeout_per_run,
            )
    _print_json(result)


def _add_online_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--knowledge-base-id", required=True)
    parser.add_argument("--api-timeout", type=float, default=120.0)


def _saved_testset_id(dataset_dir: Path) -> str:
    path = dataset_dir / "testset_response.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return str(payload["id"])
    except (FileNotFoundError, KeyError, ValueError) as exc:
        raise CMRCValidationError(f"无法从 {path} 读取 testset id，请显式传 --testset-id。") from exc


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except CMRCValidationError as exc:
        raise SystemExit(f"CMRC2018 验证失败：{exc}") from exc
