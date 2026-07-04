from types import SimpleNamespace

from app.rag.chunker import ParsedChunk
from app.rag.legal_structure import extract_legal_query_hints, legal_article_variants
from app.rag.retriever import RetrievalHit
from app.services.document_processing import _to_db_chunk
from app.services.knowledge_search import _boost_legal_hits


def test_document_processing_extracts_law_structure_metadata_into_chunk_payload():
    document = SimpleNamespace(
        id="doc-law",
        tenant_id=10000,
        knowledge_base_id="kb-law",
        title="中华人民共和国民法典_20200528.pdf",
        tag_id=None,
    )
    parsed = ParsedChunk(
        content="第一千一百六十五条 行为人因过错侵害他人民事权益造成损害的，应当承担侵权责任。",
        index=0,
        start=0,
        end=40,
        context_header="# 第一章 一般规定",
    )

    chunk = _to_db_chunk(document, parsed, 0, "child")

    assert chunk.chunk_metadata["law_name"] == "中华人民共和国民法典"
    assert chunk.chunk_metadata["chapter"] == "第一章 一般规定"
    assert chunk.chunk_metadata["article_no"] == "第一千一百六十五条"
    assert chunk.chunk_metadata["legal_structure"] is True
    assert "中华人民共和国民法典" in chunk.search_text
    assert "第一千一百六十五条" in chunk.search_text


def test_legal_boost_prioritizes_exact_article_matches():
    unrelated = RetrievalHit(
        chunk_id="chunk-unrelated",
        document_id="doc-law",
        knowledge_base_id="kb-law",
        title="中华人民共和国行政处罚法_20210122.pdf",
        context_header="# 第七章 法律责任",
        content="第八十三条 行政机关对应当予以制止和处罚的违法行为不予制止、处罚。",
        score=0.2,
        metadata={"law_name": "中华人民共和国行政处罚法", "article_no": "第八十三条"},
    )
    exact = RetrievalHit(
        chunk_id="chunk-exact",
        document_id="doc-law",
        knowledge_base_id="kb-law",
        title="中华人民共和国行政处罚法_20210122.pdf",
        context_header="# 第七章 法律责任",
        content="第七十六条 行政机关实施行政处罚，有下列情形之一，由上级行政机关责令改正。",
        score=0.01,
        metadata={"law_name": "中华人民共和国行政处罚法", "article_no": "第七十六条"},
    )

    boosted = _boost_legal_hits("请说明中华人民共和国行政处罚法第七十六条的法律责任", [unrelated, exact])

    assert boosted[0].chunk_id == "chunk-exact"
    assert boosted[0].metadata["legal_boosted"] is True
    assert boosted[0].metadata["legal_boost_bonus"] >= 0.35


def test_legal_query_hints_normalize_arabic_article_numbers():
    hints = extract_legal_query_hints("请说明中华人民共和国行政处罚法 76 条的法律责任")

    assert hints["law_name"] == "中华人民共和国行政处罚法"
    assert hints["article_no"] == "第七十六条"
    assert hints["article_no_normalized"] == "76"
    assert "第七十六条" in legal_article_variants(hints["article_no"])
    assert "第76条" in legal_article_variants(hints["article_no"])


def test_legal_query_hints_do_not_include_article_text_in_law_name():
    hints = extract_legal_query_hints("请说明中华人民共和国刑法第三百七十一条的核心法律要点")
    tenth_hints = extract_legal_query_hints("请说明中华人民共和国行政处罚法第十条的核心法律要点")

    assert hints["law_name"] == "中华人民共和国刑法"
    assert hints["article_no"] == "第三百七十一条"
    assert hints["article_no_normalized"] == "371"
    assert tenth_hints["article_no"] == "第十条"
    assert tenth_hints["article_no_normalized"] == "10"


def test_legal_query_hints_extract_piece_index_and_clean_section_title():
    piece_hints = extract_legal_query_hints("请说明中华人民共和国刑法第 3 个知识片段的核心法律要点")
    section_hints = extract_legal_query_hints("请说明中华人民共和国刑法第四节 妨害文物管理罪的核心法律要点")
    rewritten_section_hints = extract_legal_query_hints(
        "中华人民共和国刑法第四节 妨害文物管理罪 核心法律要点 适用条件 例外"
    )

    assert piece_hints["law_name"] == "中华人民共和国刑法"
    assert piece_hints["knowledge_piece_index"] == 3
    assert section_hints["law_name"] == "中华人民共和国刑法"
    assert section_hints["section"] == "第四节 妨害文物管理罪"
    assert rewritten_section_hints["section"] == "第四节 妨害文物管理罪"
