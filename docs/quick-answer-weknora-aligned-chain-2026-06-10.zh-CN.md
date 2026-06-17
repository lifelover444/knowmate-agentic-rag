# Quick Q&A WeKnora 对齐召回链路

更新日期：2026-06-17

本文记录 knowmate 当前上线版 Quick Q&A 主链路。目标是解释为什么此前复杂法律问题会把错误主题条文误选为首个上下文，以及 v0.91 后如何按 WeKnora 思路排查和修复召回。

## 上线链路

```text
用户问题
  -> Query Understand
  -> scope 校验和知识库模型配置读取
  -> over-retrieval 候选池放大
  -> Qdrant dense retrieval
  -> ParadeDB BM25 keyword retrieval
  -> low-recall query expansion
  -> weighted RRF hybrid merge
  -> deduplicate / FAQ merge
  -> mandatory rerank
  -> composite score + MMR
  -> parent-child / neighbor chunk merge
  -> context select
  -> grounded answer
  -> answer + sources + retrieval_trace
```

## 阶段说明

### 1. Query Understand

Quick Q&A 不再只在有历史会话时改写问题。每次请求都会先构造 WeKnora-style query understand prompt，要求模型返回结构化 JSON：

```json
{
  "rewrite_query": "...",
  "intent": "...",
  "image_description": ""
}
```

`rewrite_query` 用于保留实体、事实条件和检索关键词；`intent` 写入 `retrieval_trace.query_intent`，便于判断当前问题是法律责任、赔偿顺序、事实问答还是其他意图。模型输出不是合法 JSON 时不会把脏文本当检索词，而是明确记录失败并回退原始 query。

### 2. Over-retrieval

旧链路过早按公开 top-k 截断，容易让一两个语义相近但主题错误的 chunk 占位。当前内部候选池使用：

```text
over_retrieval_limit = min(max(rerank_top_k * 5, 50) * scope_count, 500)
```

也就是说，公开配置仍保持 `rerank_top_k=8`、`final_context_count=6`，但进入 vector、keyword 和 RRF 的候选池会按知识库 scope 放大，给 rerank 和 MMR 足够候选。

### 3. Hybrid / RRF

主链路固定 hybrid：

- vector：Qdrant dense retrieval。
- keyword：ParadeDB `pg_search` BM25。
- fusion：weighted RRF，默认 `rrf_k=60`、`rrf_vector_weight=0.65`、`rrf_keyword_weight=0.35`。

用户请求不能切成 vector-only 或 keyword-only；旧请求体里的 mode 字段不改变实际链路。

### 4. Low-recall Query Expansion

当初始候选不足时，系统会本地生成少量 query variants，包括停用词过滤后的关键词、分隔短语、空格短语和疑问前缀清理版本。扩展只追加 keyword 候选，使用降低后的阈值，并且继续进入 deduplicate、FAQ merge、rerank、parent/context 统一链路。

扩展阶段会写入 `retrieval_trace.stages[].name = "query_expansion"`，用于排查是原始 query 命中，还是扩展 query 补到了候选。

### 5. Rerank Composite / MMR

rerank 是必需阶段。候选不再只把 chunk content 送入模型，而是构造 enriched passage：

```text
context_header
context_content 或 content
metadata.generated_questions
图片 OCR / caption 文本
```

排序使用组合分，而不是裸 rerank 分。v0.91 起组合分加入 query lexical coverage，用于防止不包含核心检索词的高 rerank chunk 压过目标条文：

```text
composite_score = 0.3 * rerank_score + 0.1 * base_score + 0.5 * lexical_score + 0.1 * source_weight
```

FAQ 候选不使用通用 lexical 纠偏，继续由 FAQ merge / boost 策略控制。随后使用 enriched passage 的 token set 做 MMR 去冗余，避免相邻或重复 chunk 挤占最终上下文。trace 的 rerank 阶段会输出 `score_details`，包括 base、rerank、lexical、composite 和 MMR 前后数量。

### 6. Chunk Merge / Context Select

检索仍以 child chunk 为主。进入回答前：

- child 命中会扩展到 parent context。
- 短文本命中会按 `pre_chunk_id` / `next_chunk_id` 追加同文档邻居，形成更完整的 `context_content`。
- sources 保留原始命中 chunk identity，回答 prompt 使用合并后的上下文。

这对应 WeKnora `CHUNK_MERGE` 的核心目标：检索颗粒度要小，回答上下文要完整。

### 7. Answer / Sources

LLM 只基于选出的 numbered context 生成回答。返回内容包括：

- `answer`
- `sources`
- `retrieval_trace`
- `rendered_context`
- `prompt_context_summary`

sources 至少保留 document id/title、child chunk id、parent chunk id、snippet、score、rerank score、source type 和 metadata 摘要，方便用户解释“为什么引用了这段”。

## 召回差的主要原因

此前法律样例召回差，核心不是单一模型问题，而是链路缺口叠加：

1. 无历史问题没有稳定 query understand，复杂问题里的“机动车、交强险、商业三者险、赔偿顺序”没有被结构化强化。
2. RRF 前候选池太小，错误主题 chunk 一旦靠前，后续阶段缺少足够候选纠偏。
3. rerank passage 只看局部 chunk，缺少 context header、parent context 和 generated questions。
4. rerank 排序过度依赖模型分，没有把原始召回分和来源权重纳入组合判断。
5. child 命中直接进入回答时上下文太窄，容易缺赔偿顺序、保险责任等相邻信息。
6. 运行态 embedding 维度和已入库 Qdrant collection 维度不一致时，vector 阶段会直接退化为 0 命中。例如 KB 向量在 `knowmate_embeddings_1024`，但模型配置被改成 `embedding_dimension=512`，查询会查不存在的 `knowmate_embeddings_512`。

TASK-057 到 TASK-062 分别修复了链路缺口，TASK-063 使用交通事故法律夹具验收：top selected context 必须包含机动车交通事故、交强险、商业三者险等目标条文。v0.91 进一步修复真实运行态维度漂移、rerank 错排和回答 prompt 过度保守问题。

## 排障 Checklist

召回结果仍然异常时，优先看 `retrieval_trace`：

- `query_original/query_rewritten/query_intent` 是否保留关键实体和法律主题。
- `vector.keyword.rrf` 阶段是否有目标 chunk，`over_retrieval_limit` 是否被放大。
- `query_expansion` 是否触发，`added_hit_count` 是否有效。
- `vector` 阶段是否为 0。如果为 0，先检查 embedding 模型配置维度与 Qdrant collection 是否一致。
- `rerank.score_details` 中目标 chunk 的 `rerank_score/lexical_score/composite_score` 是否被错误压低。
- `parent_expand/context_select` 是否把 child 扩展到正确 parent 或邻居上下文。
- sources 的 `chunk_id/parent_chunk_id/metadata` 是否能对应到正确文档和章节。

生产环境还必须确认：

- KnowledgeQA、Embedding、Rerank 模型均已配置并可用。
- PostgreSQL 使用 ParadeDB 镜像并加载 `pg_search`。
- Qdrant collection 维度与当前 embedding 模型一致。
- 如果切换过 embedding 模型或维度，必须重处理文档或重建知识库索引，避免旧向量 collection 与新查询维度不一致。
- 文档处理已完成，child chunks 同时写入 PostgreSQL、BM25 和 Qdrant。
- ingestion 侧 `search_text` 包含 title、context header、content 和可选 generated questions。
