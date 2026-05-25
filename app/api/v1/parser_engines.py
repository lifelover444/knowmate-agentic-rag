from fastapi import APIRouter

from app.rag.parser import ParserEngineRegistry

router = APIRouter()


@router.get("")
def list_parser_engines():
    return ParserEngineRegistry().list_engines()
