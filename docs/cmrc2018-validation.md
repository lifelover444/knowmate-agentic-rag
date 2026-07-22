# CMRC2018 中文小数据集端到端验证

本方案是 KnowMate v1.1 的中文 native RAGAS 可复现验收基线；版本范围和实测结论见
[v1.1 版本说明](v1.1.md)。

本方案固定使用 CMRC2018 官方 `cmrc2018_dev.json`（即 Hugging Face 命名中的
`validation` split），从 848 篇互异 context 中用固定种子 `20240722` 选出 20 篇目标文档和
180 篇干扰文档。20 道黄金题严格来自 20 个不同目标 context。

数据源锁定到官方仓库提交 `c0eb1b6ba219847457e6af3180da722bbeb656af`，原始 dev 文件
SHA-256 是 `e9ff74231f05c230c6fa88b84441ee334d97234cbb610991cd94b82db00c7f1f`。
官方数据集采用 CC BY-SA 4.0；准备命令会同时保存来源说明与许可证全文。

## 0. 前置条件

先按项目 README 启动 PostgreSQL/ParadeDB、Redis、Qdrant、API 和 Celery worker，执行数据库迁移，
并在网页中创建一个专用知识库。该知识库必须绑定可用的 KnowledgeQA、Embedding 模型；运行
`rerank=true` 还必须配置可用的 Rerank 模型。

这次验证要求 **强制 native RAGAS**。真正执行 Evaluation 的是 Celery worker，因此必须在
worker 进程环境中设置：

```bash
export RAGAS_EVALUATOR_MODE=native
celery -A app.workers.celery_app:celery_app worker --loglevel=info --pool=solo
```

若 API 和 worker 都在本机运行，可以在另一个终端启动 API：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`native` 模式现已是严格模式：native judge 失败时评测任务直接失败并记录
`evaluator_config.mode=native_ragas_failed`，不会静默伪装成 `semantic_proxy` 成绩。

以下命令均在仓库根目录执行，把 `<KB_ID>` 替换为专用知识库 ID。

## 1. 下载并准备 200 篇纯 context

```bash
python -m scripts.cmrc2018_e2e prepare \
  --output-dir storage/cmrc2018_validation \
  --seed 20240722
```

主要产物：

- `corpus/`：恰好 200 个可上传 `.txt`，文件内容逐字节只含官方 context；
- `corpus_manifest.json`：稳定 `dataset_context_id`、官方 context ID、文件名、角色和内容哈希；
- `golden_questions.raw.json`：20 道原始黄金题及答案标注；
- `source/cmrc2018_dev.json`：校验过哈希的官方 dev 原文件；
- `SOURCE_AND_LICENSE.md` 与 `source/CMRC2018_LICENCE.txt`：来源、引用与 CC BY-SA 4.0 说明。

绝对不要手工上传 `source/`、`golden_questions.raw.json` 或之后生成的 testset JSON。上传命令只读取
`corpus_manifest.json` 并上传 `corpus/` 中列出的 200 个纯 context 文件。

## 2. 上传并等待文档处理

```bash
python -m scripts.cmrc2018_e2e upload \
  --dataset-dir storage/cmrc2018_validation \
  --base-url http://127.0.0.1:8000 \
  --knowledge-base-id <KB_ID> \
  --timeout 3600
```

脚本用稳定文件名把 `dataset_context_id` 映射到项目动态生成的 document ID；同名且大小一致的已上传
文档会复用，所以命令可恢复执行。它会轮询到全部 200 篇 `parse_status=completed`，失败或超时则非零退出。
映射保存在 `upload_state.json`。

只想先提交上传、稍后再等待时可加 `--no-wait`，但下一阶段必须在所有目标文档完成后执行。

## 3. 绑定真实答案 chunk 并导入黄金集

```bash
python -m scripts.cmrc2018_e2e bind \
  --dataset-dir storage/cmrc2018_validation \
  --base-url http://127.0.0.1:8000 \
  --knowledge-base-id <KB_ID>
```

该阶段按文件名找回目标 document，再调用 `GET /api/v1/documents/{document_id}/chunks`。对每题只从
已启用、非 parent 的 chunk 中选择真正包含官方答案原文且最接近原始 `answer_start` 的 chunk。
任意一题找不到答案 chunk 都会停止，避免把文档 ID、parent ID 或错误 chunk 当成 expected source。

产物：

- `chunk_bindings.json`：`dataset_context_id -> document_id -> chunk_id` 完整链路；
- `testset.import.json`：可直接提交给 `POST /api/v1/evaluations/testsets` 的请求体；
- `testset_response.json`：导入后的 testset ID 与服务端回包。

脚本默认调用导入 API，并在重跑时校验、复用内容完全一致的同名黄金集。只生成 JSON 而不导入可加
`--no-import`。接口本身还会再次确认每个 `expected_chunk_ids` 都属于当前知识库。

## 4. 运行 top_k=5 的 rerank A/B 与 native RAGAS 验收

```bash
python -m scripts.cmrc2018_e2e run \
  --dataset-dir storage/cmrc2018_validation \
  --base-url http://127.0.0.1:8000 \
  --knowledge-base-id <KB_ID> \
  --top-k 5 \
  --timeout-per-run 3600
```

脚本从 `testset_response.json` 读取 testset ID，依次创建两次 Evaluation：

1. `top_k=5, enable_rerank=false`；
2. `top_k=5, enable_rerank=true`。

Evaluation 服务会逐题调用现有 `QuickAnswerService.prepare_answer(...,
respect_retrieval_overrides=True)`，所以两次运行复用同一套 Quick Answer 主链路，只改变 rerank 开关。

结果写到 `storage/cmrc2018_validation/results/<UTC时间>/`：

- `rerank_off.json`、`rerank_on.json`：两次完整运行和逐题结果；
- `comparison.json`：机器可读汇总；
- `comparison.md`：指标、expected source 命中率和运行状态的易读对照表。

脚本最后强制检查两次运行的 `status=completed`，并明确检查：

```text
evaluator_config.mode == native_ragas
```

只要任一次是 `semantic_proxy`、`native_ragas_failed`、缺少 mode 或运行失败，脚本都会在保留完整结果后
以非零状态退出。`semantic_proxy` 结果绝不会被报告为原生 RAGAS。

如需显式指定 testset 或结果目录：

```bash
python -m scripts.cmrc2018_e2e run \
  --dataset-dir storage/cmrc2018_validation \
  --base-url http://127.0.0.1:8000 \
  --knowledge-base-id <KB_ID> \
  --testset-id <TESTSET_ID> \
  --output-dir storage/cmrc2018_validation/results/manual-run
```

## 5. v1.1 实际运行结果

![CMRC2018 native RAGAS 评测结果](assets/v1.1/evaluations-native-ragas-cmrc2018.png)

| 配置 | Overall | Context precision | Context recall | Faithfulness | Response relevancy | Expected source hit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `rerank=false` | 0.8769 | 0.9000 | 0.9000 | 0.8667 | 0.8653 | 100% |
| `rerank=true` | 0.8733 | 0.9000 | 0.9000 | 0.9173 | 0.7803 | 100% |

两次均为 20/20 completed、failed 0、`top_k=5`，并通过
`evaluator_config.mode == native_ragas` 硬校验。完整对照报告保存在
`storage/cmrc2018_validation/results/online-native-20260722/comparison.md`。

## 6. 结果解释边界

当前 RAGAS adapter 使用知识库自身的 `qa_model_id` 作为裁判模型，Quick Answer 也使用该知识库 QA 模型。
另外，当前实现的 `context_precision`、`context_recall`、`faithfulness` 和 `response_relevancy` 使用
native RAGAS，`factual_correctness` 仍由项目内的确定性 proxy 计算；这一点也会明确写在
`evaluator_config.metrics` 的 `factual_correctness_proxy` 中。因此，这套 20 题运行适合验证数据、上传、
检索、重排、回答和 RAGAS 调用能否完整闭环，也适合相同环境下的工程回归比较；它不是使用独立 judge、
全指标原生实现、重复实验和统计显著性分析的正式科研分数。正式实验应另行增加独立裁判模型、固定模型版本/
温度、重复运行和置信区间。

## 7. 离线验证

数据转换、chunk 映射与 native 模式防回退无需真实 API Key 即可测试：

```bash
python -m pytest -q tests/test_cmrc2018_validation.py tests/test_v10_ragas_evaluations.py
ruff check app/services/cmrc2018_validation.py scripts/cmrc2018_e2e.py tests/test_cmrc2018_validation.py
python -m compileall app scripts tests
```
