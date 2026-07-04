import argparse
import json

from app.core.config import get_settings
from app.db.session import make_session_factory
from app.integrations.vector_store import VectorStoreRegistry
from app.services.legal_metadata import LegalMetadataBackfillService


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill legal metadata into existing chunks.")
    parser.add_argument("--knowledge-base-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-vector-sync", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    settings = get_settings()
    session_factory = make_session_factory(settings)
    vector_store = None if args.no_vector_sync else VectorStoreRegistry(settings).build("qdrant")
    with session_factory() as db:
        result = LegalMetadataBackfillService(db, settings, vector_store=vector_store).backfill_knowledge_base(
            args.knowledge_base_id,
            dry_run=args.dry_run,
            sync_vector=not args.no_vector_sync,
            limit=args.limit,
        )
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
