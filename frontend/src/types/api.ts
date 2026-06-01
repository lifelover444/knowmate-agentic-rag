export type ModelType = "KnowledgeQA" | "Embedding" | "Rerank" | "VLLM" | "ASR";

export interface ModelRead {
  id: string;
  tenant_id: number;
  name: string;
  type: ModelType | string;
  provider: string;
  source: string;
  base_url: string;
  model_name: string;
  embedding_dimension?: number | null;
  status: string;
  is_builtin: boolean;
  api_key_configured: boolean;
  api_key_last4?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ModelPayload {
  name: string;
  type: ModelType | string;
  provider: string;
  source: string;
  base_url: string;
  api_key?: string;
  model_name: string;
  embedding_dimension?: number | null;
  status?: string;
}

export interface ModelTestPayload extends ModelPayload {
  model_id?: string;
}

export interface RetrievalConfig {
  retrieval_mode: string;
  embedding_top_k: number;
  vector_threshold: number;
  keyword_threshold: number;
  rerank_top_k: number;
  rerank_threshold: number;
  rerank_model_id?: string | null;
  enable_rerank: boolean;
  rrf_k: number;
  rrf_vector_weight: number;
  rrf_keyword_weight: number;
}

export interface ChunkingConfig {
  strategy: string;
  chunk_size: number;
  chunk_overlap: number;
  separators: string[];
  token_limit: number;
  languages: string[];
  enable_parent_child: boolean;
  parent_chunk_size: number;
  child_chunk_size: number;
}

export interface IndexingStrategy {
  enable_vector: boolean;
  enable_keyword: boolean;
  enable_parent_child: boolean;
  enable_rerank: boolean;
  enable_wiki: boolean;
  enable_knowledge_graph: boolean;
}

export interface FAQConfig {
  index_mode: "question_only" | "question_answer" | string;
  question_index_mode: "combined" | "separate" | string;
}

export interface KnowledgeBaseCapabilities {
  document: boolean;
  faq: boolean;
  vector: boolean;
  keyword: boolean;
  parent_child: boolean;
  rerank: boolean;
  wiki: boolean;
  graph: boolean;
}

export interface ParserEngineRule {
  file_types: string[];
  engine: string;
}

export interface ParserEngine {
  name: string;
  label?: string;
  available: boolean;
  file_types?: string[];
  description?: string | null;
}

export interface KnowledgeBaseRead {
  id: string;
  tenant_id: number;
  name: string;
  description?: string | null;
  kb_type: "document" | "faq" | string;
  chunking_config: ChunkingConfig | Record<string, unknown>;
  parser_engine_rules?: ParserEngineRule[] | null;
  faq_config?: FAQConfig | null;
  indexing_strategy: IndexingStrategy | Record<string, unknown>;
  vector_store_id?: string | null;
  embedding_model_id: string;
  summary_model_id: string;
  document_count: number;
  chunk_count: number;
  processing_count: number;
  capabilities: KnowledgeBaseCapabilities;
  is_pinned: boolean;
  pinned_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBasePayload {
  name: string;
  description?: string | null;
  kb_type?: "document" | "faq" | string;
  embedding_model_id?: string | null;
  summary_model_id?: string | null;
  chunking_config: ChunkingConfig;
  parser_engine_rules: ParserEngineRule[];
  faq_config?: FAQConfig | null;
  indexing_strategy?: IndexingStrategy;
  vector_store_id?: string | null;
}

export interface KnowledgeTagRead {
  id: string;
  tenant_id: number;
  knowledge_base_id: string;
  name: string;
  color?: string | null;
  sort_order: number;
  knowledge_count: number;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeTagPayload {
  name: string;
  color?: string | null;
  sort_order?: number;
}

export interface BatchTagAssignmentResponse {
  updated: number;
}

export interface DocumentRead {
  id: string;
  tenant_id: number;
  knowledge_base_id: string;
  type: string;
  source_type: string;
  title: string;
  source: string;
  parse_status: "pending" | "processing" | "completed" | "failed" | string;
  enable_status: string;
  file_name?: string | null;
  file_type?: string | null;
  file_size: number;
  storage_size: number;
  tag_id?: string | null;
  embedding_model_id?: string | null;
  chunk_count: number;
  task_status?: string | null;
  processed_at?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProcessingTaskRead {
  id: string;
  tenant_id: number;
  knowledge_base_id?: string | null;
  document_id?: string | null;
  task_type: string;
  status: string;
  progress: number;
  error_message?: string | null;
  batch_summary?: TaskBatchSummary | null;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskFailure {
  task_id: string;
  document_id?: string | null;
  error_message: string;
}

export interface TaskBatchSummary {
  total: number;
  queued: number;
  processing: number;
  completed: number;
  failed: number;
  failures: TaskFailure[];
}

export interface BatchDocumentFailure {
  document_id: string;
  reason: string;
}

export interface BatchDocumentResponse {
  deleted: number;
  queued: number;
  requested: number;
  succeeded: number;
  failed: number;
  failures: BatchDocumentFailure[];
  task_ids: string[];
}

export interface VectorStoreRead {
  id: string;
  tenant_id: number;
  name: string;
  provider: string;
  config_json: Record<string, unknown>;
  status: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface VectorStorePayload {
  name: string;
  provider: string;
  config_json: Record<string, unknown>;
  status?: string;
  is_default?: boolean;
}

export interface FAQEntryRead {
  id: string;
  tenant_id: number;
  knowledge_base_id: string;
  knowledge_id: string;
  question: string;
  similar_questions: string[];
  answer: string;
  metadata?: Record<string, unknown> | null;
  tag_id?: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export type FAQExportFormat = "csv" | "xlsx";

export interface FAQImportFailure {
  row: number;
  question?: string | null;
  error: string;
}

export interface FAQImportResult {
  total: number;
  imported: number;
  failed: number;
  mode: "append" | "replace";
  failures: FAQImportFailure[];
}

export interface ChunkRead {
  id: string;
  tenant_id: number;
  knowledge_base_id: string;
  knowledge_id: string;
  content: string;
  chunk_index: number;
  is_enabled: boolean;
  start_at: number;
  end_at: number;
  pre_chunk_id?: string | null;
  next_chunk_id?: string | null;
  chunk_type: string;
  parent_chunk_id?: string | null;
  tag_id?: string | null;
  context_header?: string | null;
  metadata?: Record<string, unknown> | null;
  images?: unknown[] | null;
  created_at: string;
}

export interface DocumentPreviewChunk {
  id: string;
  chunk_index: number;
  chunk_type: string;
  start_at: number;
  end_at: number;
  context_header?: string | null;
  content_preview: string;
}

export interface DocumentPreviewRead {
  id: string;
  tenant_id: number;
  knowledge_base_id: string;
  title: string;
  file_name?: string | null;
  file_type?: string | null;
  status: string;
  summary?: string | null;
  content_preview: string;
  chunks: DocumentPreviewChunk[];
  error_message?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface ProcessingSpanRead {
  span_id: string;
  parent_span_id?: string | null;
  name: string;
  kind: string;
  status: "pending" | "running" | "done" | "failed" | "cancelled" | "skipped" | string;
  input?: Record<string, unknown> | null;
  output?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  error_code?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms: number;
}

export interface ProcessingSpanTimeline {
  knowledge_id: string;
  attempt: number;
  root: ProcessingSpanRead;
  stages: ProcessingSpanRead[];
}

export interface SourceRead {
  document_id: string;
  knowledge_base_id: string;
  knowledge_base_name?: string | null;
  chunk_id: string;
  title?: string | null;
  content: string;
  score: number;
  context_header?: string | null;
  parent_chunk_id?: string | null;
  chunk_type?: string | null;
  metadata?: Record<string, unknown> | null;
  retrieval_method?: string | null;
  vector_score?: number | null;
  keyword_score?: number | null;
  rrf_score?: number | null;
  rerank_score?: number | null;
  context_chunk_id?: string | null;
  context_content?: string | null;
}

export interface ChatSettings {
  mode?: string | null;
  top_k?: number | null;
  enable_rerank?: boolean | null;
  temperature?: number | null;
  system_prompt?: string | null;
  enable_query_rewrite?: boolean;
}

export interface MentionedItem {
  id: string;
  name: string;
  type: "kb" | "file" | string;
  kb_type?: string | null;
}

export interface ChatMessageRead {
  id: string;
  tenant_id: number;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  original_query?: string | null;
  rewritten_query?: string | null;
  mentioned_items?: MentionedItem[];
  sources: SourceRead[];
  retrieval_trace?: Record<string, unknown> | null;
  model_config?: Record<string, unknown> | null;
  status: string;
  error_message?: string | null;
  created_at: string;
}

export interface ChatSessionRead {
  id: string;
  tenant_id: number;
  knowledge_base_id: string;
  title: string;
  is_pinned: boolean;
  settings: ChatSettings | Record<string, unknown>;
  last_message_at: string;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionDetail extends ChatSessionRead {
  messages: ChatMessageRead[];
}

export interface ChatSessionListResponse {
  items: ChatSessionRead[];
}

export interface ChatSessionBatchDeleteFailure {
  session_id: string;
  reason: string;
}

export interface ChatSessionBatchDeleteResponse {
  requested: number;
  deleted: number;
  failed: number;
  failures: ChatSessionBatchDeleteFailure[];
}

export interface ChatMessageListResponse {
  items: ChatMessageRead[];
}

export interface RecommendedQuestionRead {
  question: string;
  source_type: string;
  knowledge_base_id: string;
  knowledge_id?: string | null;
  chunk_id?: string | null;
  faq_id?: string | null;
  title?: string | null;
}

export interface RecommendedQuestionListResponse {
  items: RecommendedQuestionRead[];
}

export interface QuickAnswerResponse {
  answer: string;
  sources: SourceRead[];
}

export interface KnowledgeSearchResponse {
  hits: SourceRead[];
}

export interface FAQSearchTestResult extends SourceRead {
  tag_id?: string | null;
}

export interface PreviewChunk {
  seq: number;
  start: number;
  end: number;
  size_chars: number;
  size_tokens_approx: number;
  context_header?: string | null;
  content: string;
}

export interface PreviewChunkingResponse {
  selected_tier: string;
  tier_chain: string[];
  rejected: Record<string, unknown>[];
  profile: Record<string, number>;
  chunks: PreviewChunk[];
  stats: {
    count: number;
    avg_chars: number;
    min_chars: number;
    max_chars: number;
    stddev_chars: number;
    truncated_to?: number | null;
  };
}
