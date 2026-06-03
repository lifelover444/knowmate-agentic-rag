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

export interface ModelProviderCredentialField {
  name: string;
  label: string;
  sensitive: boolean;
  required: boolean;
}

export interface ModelProviderPreset {
  value: string;
  label: string;
  description: string;
  model_types: string[];
  default_urls: Record<string, string>;
  default_models: Record<string, string>;
  embedding_dimensions: Record<string, number>;
  credential_fields: ModelProviderCredentialField[];
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
  status?: string;
  error_message?: string | null;
  fix_suggestion?: string | null;
}

export interface RuntimeStatus {
  system: Record<string, unknown>;
  database: Record<string, unknown>;
  storage: Record<string, unknown>;
  storage_providers?: RuntimeProviderStatus[];
  vector_store: Record<string, unknown>;
  vector_stores?: RuntimeVectorStoreStatus;
  model_configs?: RuntimeModelConfigStatus;
  parser_engines: ParserEngine[];
  fix_suggestions?: string[];
}

export interface RuntimeProviderStatus {
  provider: string;
  label?: string;
  status: string;
  available?: boolean;
  description?: string | null;
  path?: string | null;
  fix_suggestion?: string | null;
}

export interface RuntimeVectorStoreStatus {
  registered_count: number;
  items: Array<Record<string, unknown>>;
  default?: Record<string, unknown> | null;
  fix_suggestion?: string | null;
}

export interface RuntimeModelConfigStatus {
  summary: {
    total: number;
    active: number;
    api_key_configured: number;
  };
  required_types: Record<
    string,
    {
      status: string;
      count: number;
      active_model_id?: string | null;
      provider?: string | null;
      model_name?: string | null;
      api_key_configured: boolean;
      api_key_last4?: string | null;
      fix_suggestion?: string | null;
    }
  >;
  items: Array<Record<string, unknown>>;
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

export interface DocumentMoveFailure {
  document_id: string;
  reason: string;
}

export interface DocumentMoveResponse {
  requested: number;
  moved: number;
  failed: number;
  failures: DocumentMoveFailure[];
  target_kb_id: string;
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

export interface VectorStoreFieldSpec {
  name: string;
  label: string;
  field_type: string;
  required: boolean;
  sensitive: boolean;
  default?: unknown;
}

export interface VectorStoreTypeRead {
  type: string;
  label: string;
  status: "available" | "planned" | "unavailable" | string;
  description: string;
  connection_fields: VectorStoreFieldSpec[];
  index_fields: VectorStoreFieldSpec[];
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
  is_recommended: boolean;
  created_at: string;
  updated_at: string;
}

export type FAQExportFormat = "csv" | "xlsx";

export interface FAQFieldUpdate {
  enabled?: boolean;
  is_enabled?: boolean;
  recommended?: boolean;
  is_recommended?: boolean;
  tag_id?: string | null;
}

export interface FAQFieldBatchUpdateRequest {
  by_id?: Record<string, FAQFieldUpdate>;
  by_tag?: Record<string, FAQFieldUpdate>;
  exclude_ids?: string[];
}

export interface FAQFieldBatchFailure {
  faq_id: string;
  reason: string;
}

export interface FAQFieldBatchUpdateResponse {
  requested: number;
  succeeded: number;
  failed: number;
  failures: FAQFieldBatchFailure[];
  error_summary?: string | null;
}

export interface FAQImportFailure {
  row: number;
  question?: string | null;
  error: string;
}

export interface FAQImportResult {
  task_id?: string;
  knowledge_base_id?: string;
  status?: string;
  progress?: number;
  total: number;
  processed?: number;
  succeeded?: number;
  imported: number;
  failed: number;
  errors?: FAQImportFailure[];
  mode: "append" | "replace";
  import_mode?: "append" | "replace" | string;
  display_status?: "open" | "close" | string;
  error_summary?: string | null;
  processing_time_ms?: number;
  imported_at?: string | null;
  failures: FAQImportFailure[];
}

export interface FAQImportProgress extends FAQImportResult {
  task_id: string;
  knowledge_base_id: string;
  status: string;
  progress: number;
  processed: number;
  succeeded: number;
  display_status: "open" | "close" | string;
}

export interface ChunkRead {
  id: string;
  tenant_id: number;
  knowledge_base_id: string;
  knowledge_id: string;
  content: string;
  search_text?: string | null;
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

export interface GeneratedQuestion {
  id: string;
  question: string;
}

export interface ChunkUpdatePayload {
  content?: string;
  search_text?: string | null;
  metadata?: Record<string, unknown> | null;
  is_enabled?: boolean;
}

export interface ChunkUpdateResponse {
  chunk: ChunkRead;
  requires_reindex: boolean;
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

export interface RetrievalTraceStage {
  name: string;
  status: string;
  duration_ms?: number | null;
  input?: Record<string, unknown> | null;
  output?: Record<string, unknown> | null;
  error_message?: string | null;
}

export interface RetrievalDiagnostics {
  query?: string;
  mode?: string | null;
  requested_top_k?: number | null;
  effective_top_k?: number | null;
  knowledge_base_ids?: string[];
  knowledge_ids?: string[];
  enable_rerank?: boolean;
  hit_count?: number;
  stages: RetrievalTraceStage[];
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

export interface AttachmentInput {
  filename: string;
  content: string;
  mime_type?: string | null;
  size?: number | null;
  truncated?: boolean;
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
  attachments?: AttachmentInput[];
  sources: SourceRead[];
  retrieval_trace?: (Record<string, unknown> & { stages?: RetrievalTraceStage[]; diagnostics?: RetrievalDiagnostics }) | null;
  rendered_context?: string | null;
  prompt_context_summary?: string | null;
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
  last_request_state: Record<string, unknown>;
  last_message_at: string;
  created_at: string;
  updated_at: string;
}

export interface ChatStopResponse {
  session_id: string;
  stopped: boolean;
  message: string;
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

export interface MessageSearchResultItem {
  session_id: string;
  session_title: string;
  query_content: string;
  answer_content: string;
  answer_snippet: string;
  score: number;
  match_type: string;
  created_at: string;
  message_ids: string[];
}

export interface MessageSearchResponse {
  items: MessageSearchResultItem[];
  total: number;
}

export interface ChatHistoryStats {
  enabled: boolean;
  searchable: boolean;
  session_count: number;
  message_count: number;
  last_message_at?: string | null;
  indexed_message_count: number;
  has_indexed_messages: boolean;
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
  retrieval_trace?: (Record<string, unknown> & { stages?: RetrievalTraceStage[]; diagnostics?: RetrievalDiagnostics }) | null;
}

export interface KnowledgeSearchResponse {
  hits: SourceRead[];
  diagnostics?: RetrievalDiagnostics | null;
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

export interface ChunkerDocProfile {
  total_chars: number;
  total_lines: number;
  avg_line_len: number;
  std_line_len: number;
  md_heading_counts: Record<string, number>;
  md_heading_total: number;
  numbered_section_count: number;
  all_caps_short_line_count: number;
  blank_paragraph_breaks: number;
  form_feed_count: number;
  visual_sep_count: number;
  german_chapter_count: number;
  english_chapter_count: number;
  chinese_chapter_count: number;
  repeated_footer_count: number;
  has_tables: boolean;
  has_code: boolean;
  code_ratio: number;
  detected_langs: string[];
}

export interface ChunkerProtectedBlocks {
  formula: number;
  image: number;
  markdown_link: number;
  table: number;
  code: number;
  total: number;
  total_chars: number;
}

export interface PreviewChunkingResponse {
  selected_tier: string;
  tier_chain: string[];
  rejected: Record<string, unknown>[];
  profile: ChunkerDocProfile;
  protected_blocks: ChunkerProtectedBlocks;
  token_limit_applied: boolean;
  token_limit_reason: string;
  requested_chunk_size: number;
  effective_chunk_size: number;
  fallback_tier?: string | null;
  chunks: PreviewChunk[];
  stats: {
    count: number;
    avg_chars: number;
    min_chars: number;
    max_chars: number;
    stddev_chars: number;
    avg_tokens: number;
    min_tokens: number;
    max_tokens: number;
    stddev_tokens: number;
    token_limit?: number | null;
    size_distribution: Record<string, number>;
    truncated_to?: number | null;
  };
}
