// Backend API types matching FastAPI schemas

export type ProcessingStatus = 
  'queued' | 
  'parsing' | 
  'parsed' | 
  'classifying' | 
  'classified' | 
  'indexing' | 
  'indexed' | 
  'failed';

export interface Citation {
  doc: string;
  document_name?: string;
  page: number;
  chunk_text?: string;
  thumbnail_url?: string;
  score?: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp: Date;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  document_ids?: string[];
  top_k?: number;
  history?: Array<{ role: string; content: string }>;
}

export interface ChatResponse {
  session_id: string;
  answer: string;
  citations: Citation[];
  used_documents?: string[];
  confidence?: number;
  needs_more_info?: boolean;
}

export interface UploadStatus {
  job_id: string;
  status: ProcessingStatus;
  completed_files: number;
  total_files: number;
  current_file?: string;
  error?: string;
  started_at?: string;
  updated_at?: string;
}

export interface SingleUploadResponse {
  job_id: string;
  document_id: string;
  filename: string;
  status: ProcessingStatus;
  message: string;
}

export interface BulkUploadResponse {
  job_id: string;
  files_accepted: string[];
  document_ids: string[];
  total_files: number;
  status: ProcessingStatus;
}

export interface DocumentSummary {
  document_id: string;
  filename: string;
  document_type?: string;
  topic?: string;
  sensitivity_level?: string;
  page_count: number;
  status: ProcessingStatus;
  uploaded_at: string;
}

export interface DocumentDetail extends DocumentSummary {
  language?: string;
  full_text?: string;
  page_images: string[];
  metadata: Record<string, unknown>;
}

export interface ApiError {
  code: string;
  message: string;
}
