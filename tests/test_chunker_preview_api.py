def test_chunker_preview_api_returns_diagnostics(client):
    response = client.post(
        "/api/v1/chunker/preview",
        json={
            "text": "# 指南\n\n内容一。\n\n## 安装\n\n安装说明。\n\n## 使用\n\n使用说明。\n\n## 维护\n\n维护说明。",
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
    assert payload["stats"]["count"] == len(payload["chunks"])
    assert payload["chunks"][0]["size_chars"] == len(payload["chunks"][0]["content"])


def test_parser_engines_api_returns_builtin_engine(client):
    response = client.get("/api/v1/parser-engines")

    assert response.status_code == 200
    payload = response.json()
    builtin = next(engine for engine in payload if engine["name"] == "builtin")
    assert "pdf" in builtin["file_types"]
    assert builtin["available"] is True
