import argparse
import json

from app.core.config import get_settings
from app.db.session import make_session_factory
from app.integrations.vector_store import VectorStoreRegistry
from app.services.evaluation_ab import EvaluationABService, parse_variant


def main() -> None:
    parser = argparse.ArgumentParser(description="Run A/B evaluation reports for a knowledge base testset.")
    parser.add_argument("--knowledge-base-id", required=True)
    parser.add_argument("--testset-id", required=True)
    parser.add_argument("--variant", action="append", default=[])
    parser.add_argument("--tag", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--execute-evaluation", action="store_true")
    parser.add_argument("--retrieval-limit", type=int, default=10)
    parser.add_argument("--precision-at", type=int, default=5)
    parser.add_argument("--full-output", action="store_true")
    args = parser.parse_args()

    variants = [parse_variant(value) for value in args.variant] or [
        parse_variant("topk5:top_k=5,rerank=false"),
    ]
    settings = get_settings()
    session_factory = make_session_factory(settings)
    vector_store = VectorStoreRegistry(settings).build("qdrant")
    with session_factory() as db:
        service = EvaluationABService(db, settings, vector_store=vector_store)
        report = service.run_report(
            knowledge_base_id=args.knowledge_base_id,
            testset_id=args.testset_id,
            variants=variants,
            tag=args.tag,
            execute_evaluation=args.execute_evaluation,
            retrieval_limit=args.retrieval_limit,
            precision_at=args.precision_at,
        )
        if args.output:
            service.write_report(report, args.output)
    display_report = report if args.full_output or not args.output else _summary_report(report)
    print(json.dumps(display_report, ensure_ascii=False, indent=2))


def _summary_report(report: dict) -> dict:
    return {
        key: report.get(key)
        for key in ("knowledge_base_id", "testset_id", "tag", "execute_evaluation", "retrieval_limit", "precision_at")
    } | {
        "duration_ms": report.get("duration_ms"),
        "variants": [
            {
                key: variant.get(key)
                for key in (
                    "variant",
                    "top_k",
                    "enable_rerank",
                    "run_id",
                    "overall",
                    "metrics",
                    "recall_at_10",
                    "precision_at_5",
                    "miss_count",
                    "failed_count",
                    "duration_ms",
                )
            }
            for variant in report.get("variants", [])
        ],
    }


if __name__ == "__main__":
    main()
