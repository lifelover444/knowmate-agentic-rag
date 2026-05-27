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
  chunking_config: ChunkingConfig | Record<string, unknown>;
  parser_engine_rules?: ParserEngineRule[] | null;
  embedding_model_id: string;
  summary_model_id: string;
  document_count: number;
  chunk_count: number;
  processing_count: number;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBasePayload {
  name: string;
  description?: string | null;
  embedding_model_id?: string | null;
  summary_model_id?: string | null;
  chunking_config: ChunkingConfig;
  parser_engine_rules: ParserEngineRule[];
}

export interface DocumentRead {
  id: string;
  tenant_id: number;
  knowledge_base_id: string;
  type: string;
  title: string;
  source: string;
  parse_status: "pending" | "processing" | "completed" | "failed" | string;
  enable_status: string;
  file_name?: string | null;
  file_type?: string | null;
  file_size: number;
  storage_size: number;
  processed_at?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
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
  context_header?: string | null;
  metadata?: Record<string, unknown> | null;
  images?: unknown[] | null;
  created_at: string;
}

export interface SourceRead {
  document_id: string;
  knowledge_base_id: string;
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

export interface QuickAnswerResponse {
  answer: string;
  sources: SourceRead[];
}

export interface KnowledgeSearchResponse {
  hits: SourceRead[];
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
