def test_chunker_preview_api_returns_diagnostics(client):
    table = "| 字段 | 说明 |\n| --- | --- |\n| name | 名称 |"
    code = "```python\nprint('hello')\n```"
    response = client.post(
        "/api/v1/chunker/preview",
        json={
            "text": (
                "# 指南\n\n内容一。\n\n## 安装\n\n安装说明。\n\n## 使用\n\n"
                f"使用说明。\n\n{table}\n\n## 维护\n\n维护说明。\n\n{code}"
            ),
            "chunking_config": {
                "strategy": "auto",
                "chunk_size": 80,
                "chunk_overlap": 10,
                "separators": ["\n\n", "\n", "。"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_tier"] == "heading"
    assert payload["tier_chain"][0] == "heading"
    assert payload["profile"]["md_heading_total"] >= 3
    assert payload["profile"]["has_tables"] is True
    assert payload["profile"]["has_code"] is True
    assert payload["protected_blocks"]["table"] >= 1
    assert payload["protected_blocks"]["code"] >= 1
    assert payload["protected_blocks"]["total"] >= 2
    assert payload["stats"]["count"] == len(payload["chunks"])
    assert payload["stats"]["size_distribution"]["small"] >= 0
    assert payload["stats"]["size_distribution"]["target"] >= 0
    assert payload["stats"]["size_distribution"]["large"] >= 0
    assert payload["stats"]["avg_tokens"] >= 1
    assert payload["stats"]["max_tokens"] >= payload["stats"]["min_tokens"]
    assert payload["chunks"][0]["size_chars"] == len(payload["chunks"][0]["content"])
    assert payload["chunks"][0]["start"] <= payload["chunks"][0]["end"]


def test_chunker_preview_api_returns_token_limit_diagnostics(client):
    response = client.post(
        "/api/v1/chunker/preview",
        json={
            "text": "密集中文内容" * 240,
            "chunking_config": {
                "strategy": "legacy",
                "chunk_size": 10000,
                "chunk_overlap": 20,
                "token_limit": 100,
                "languages": ["zh"],
                "separators": ["\n\n", "\n", "。"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_limit_applied"] is True
    assert payload["requested_chunk_size"] == 10000
    assert payload["effective_chunk_size"] < 10000
    assert "token_limit=100" in payload["token_limit_reason"]
    assert payload["stats"]["token_limit"] == 100
    assert payload["stats"]["max_tokens"] <= 120


def test_parser_engines_api_returns_builtin_engine(client):
    response = client.get("/api/v1/parser-engines")

    assert response.status_code == 200
    payload = response.json()
    builtin = next(engine for engine in payload if engine["name"] == "builtin")
    assert "pdf" in builtin["file_types"]
    assert builtin["available"] is True
