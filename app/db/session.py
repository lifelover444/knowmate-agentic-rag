from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.models import Base, Tenant


def make_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    resolved = settings or get_settings()
    kwargs = {}
    if resolved.database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(resolved.database_url, pool_pre_ping=True, **kwargs)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_database(session_factory: sessionmaker[Session], settings: Settings) -> None:
    engine = session_factory.kw["bind"]
    Base.metadata.create_all(bind=engine)
    with session_factory() as db:
        if db.get(Tenant, settings.default_tenant_id) is None:
            db.add(Tenant(id=settings.default_tenant_id, name="default", description="knowmate v1 default tenant"))
            db.commit()


def get_db() -> Generator[Session, None, None]:
    settings = get_settings()
    session_factory = make_session_factory(settings)
    with session_factory() as db:
        yield db
