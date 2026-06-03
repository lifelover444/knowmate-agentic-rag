from app.rag.chunker import (
    AdaptiveTextChunker,
    ChunkingConfig,
    approx_token_count,
    chars_for_token_limit,
    detect_language,
    split_parent_child,
)


def test_heading_strategy_preserves_heading_context():
    text = "\n\n".join(
        [
            "# 产品手册",
            "总览内容",
            "## 安装",
            "安装步骤一。安装步骤二。",
            "## 使用",
            "使用说明一。使用说明二。",
            "## 维护",
            "维护说明一。维护说明二。",
        ]
    )

    chunks, diagnostics = AdaptiveTextChunker(
        ChunkingConfig(strategy="auto", chunk_size=80)
    ).split_with_diagnostics(text)

    assert diagnostics.selected_tier == "heading"
    assert any(chunk.context_header and "## 安装" in chunk.context_header for chunk in chunks)
    assert all(chunk.end - chunk.start == len(chunk.content) for chunk in chunks)


def test_heuristic_strategy_splits_pdf_like_sections():
    text = "\f".join(
        [
            "第一章 总则\n这里是第一章内容。" * 8,
            "第二章 处理规则\n这里是第二章内容。" * 8,
            "第三章 法律责任\n这里是第三章内容。" * 8,
        ]
    )

    chunks, diagnostics = AdaptiveTextChunker(
        ChunkingConfig(strategy="auto", chunk_size=120)
    ).split_with_diagnostics(text)

    assert diagnostics.selected_tier == "heuristic"
    assert len(chunks) >= 3
    assert any("第二章" in chunk.content for chunk in chunks)


def test_legacy_strategy_respects_protected_blocks_and_overlap():
    table = "| 姓名 | 年龄 |\n| --- | --- |\n| 张三 | 18 |\n| 李四 | 20 |"
    code = "```python\nprint('hello')\n```"
    text = f"开头说明。\n\n{table}\n\n中间说明。" * 4 + f"\n\n{code}\n\n结尾说明。"

    chunks, diagnostics = AdaptiveTextChunker(
        ChunkingConfig(strategy="legacy", chunk_size=90, chunk_overlap=20)
    ).split_with_diagnostics(text)

    assert diagnostics.selected_tier == "legacy"
    assert any(table in chunk.content for chunk in chunks)
    assert any(code in chunk.content for chunk in chunks)
    assert all(not chunk.content.startswith(("\n", "。", " ")) for chunk in chunks)


def test_parent_child_chunking_links_children_to_parent_indexes():
    text = "\n\n".join([f"## 第{index}节\n" + "内容。" * 80 for index in range(1, 5)])

    result = split_parent_child(
        text,
        parent_config=ChunkingConfig(strategy="heading", chunk_size=450, chunk_overlap=40),
        child_config=ChunkingConfig(strategy="legacy", chunk_size=120, chunk_overlap=20),
    )

    assert result.parents
    assert result.children
    assert {child.parent_index for child in result.children} <= set(range(len(result.parents)))
    assert any(child.context_header for child in result.children)


def test_token_limit_uses_language_budget_and_records_diagnostics():
    english_budget = chars_for_token_limit(100, "en")
    chinese_budget = chars_for_token_limit(100, "zh")

    assert chinese_budget < english_budget
    assert detect_language("Hello 世界，这是一段 mixed text") == "mixed"
    assert approx_token_count("pneumonoultramicroscopicsilicovolcanoconiosis" * 4, "en") > 0

    text = "密集中文内容" * 240
    chunks, diagnostics = AdaptiveTextChunker(
        ChunkingConfig(strategy="legacy", chunk_size=10000, chunk_overlap=20, token_limit=100, languages=["zh"])
    ).split_with_diagnostics(text)

    assert diagnostics.token_limit_applied is True
    assert diagnostics.requested_chunk_size == 10000
    assert diagnostics.effective_chunk_size == chinese_budget
    assert "token_limit=100" in diagnostics.token_limit_reason
    assert all(approx_token_count(chunk.embedding_content(), "zh") <= 120 for chunk in chunks)


def test_token_limit_preserves_protected_table_and_code_blocks():
    table = "| 字段 | 说明 |\n| --- | --- |\n| name | 用户名称 |\n| email | 用户邮箱 |"
    code = "```python\nfor index in range(20):\n    print(index)\n```"
    text = ("普通说明。" * 80) + f"\n\n{table}\n\n" + ("更多说明。" * 80) + f"\n\n{code}\n\n" + ("结尾说明。" * 80)

    chunks, diagnostics = AdaptiveTextChunker(
        ChunkingConfig(strategy="legacy", chunk_size=10000, chunk_overlap=0, token_limit=80, languages=["zh"])
    ).split_with_diagnostics(text)

    assert diagnostics.token_limit_applied is True
    assert any(table in chunk.content for chunk in chunks)
    assert any(code in chunk.content for chunk in chunks)
