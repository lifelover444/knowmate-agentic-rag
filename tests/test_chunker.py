from app.rag.chunker import (
    AdaptiveTextChunker,
    ChunkingConfig,
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
