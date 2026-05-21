from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session


def get_db(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as db:
        yield db


def get_settings(request: Request):
    return request.app.state.settings


def get_embedder(request: Request):
    return request.app.state.embedder


def get_chat_model(request: Request):
    return request.app.state.chat_model


def get_vector_store(request: Request):
    return request.app.state.vector_store
