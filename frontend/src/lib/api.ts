import axios, { AxiosError } from 'axios';
import type {
  ChatRequest,
  ChatResponse,
  UploadStatus,
  SingleUploadResponse,
  BulkUploadResponse,
  DocumentSummary,
  ApiError,
} from '@/types/chat';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || '',
  },
});


// Interceptor for error logging
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    const apiError: ApiError = {
      code: error.response?.data?.code || 'UNKNOWN_ERROR',
      message: error.response?.data?.message || error.message || 'An unexpected error occurred',
    };
    console.error('[API Error]', apiError);
    return Promise.reject(apiError);
  }
);

// ============================================================
// Chat API
// ============================================================
export const chatApi = {
  sendMessage: async (
  message: string,
  sessionId?: string,
  documentIds?: string[],
  history?: Array<{ role: string; content: string }>
): Promise<ChatResponse> => {
    const payload: ChatRequest = {
      message,
      session_id: sessionId,
      document_ids: documentIds,
      top_k: 5,
      history,
    };
    const response = await api.post<ChatResponse>('/api/chat', payload);
    return response.data;
  },
};

// ============================================================
// Upload API
// ============================================================
export const uploadApi = {
  uploadSingle: async (file: File): Promise<SingleUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<SingleUploadResponse>('/api/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  uploadBulk: async (files: File[]): Promise<BulkUploadResponse> => {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });
    const response = await api.post<BulkUploadResponse>('/api/upload-bulk', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  getJobStatus: async (jobId: string): Promise<UploadStatus> => {
    const response = await api.get<UploadStatus>(`/api/upload/${jobId}/status`);
    return response.data;
  },

  pollJobStatus: async (
    jobId: string,
    onStatusUpdate: (status: UploadStatus) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 120
  ): Promise<UploadStatus> => {
    let attempts = 0;
    let status: UploadStatus;

    const poll = async (): Promise<UploadStatus> => {
      status = await uploadApi.getJobStatus(jobId);
      onStatusUpdate(status);

      if (status.status === 'indexed' || status.status === 'failed') {
        return status;
      }

      if (attempts >= maxAttempts) {
        throw { code: 'TIMEOUT', message: 'Max polling attempts reached' };
      }

      attempts++;
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
      return poll();
    };

    return poll();
  },
};

// ============================================================
// Documents API
// ============================================================
export const documentsApi = {
  list: async (): Promise<DocumentSummary[]> => {
    const response = await api.get<DocumentSummary[]>('/api/documents');
    return response.data;
  },

  getThumbnailUrl: (documentId: string, pageNumber: number): string => {
    return `${BASE_URL}/api/documents/${documentId}/page/${pageNumber}/thumbnail`;
  },

  getFullPageUrl: (documentId: string, pageNumber: number): string => {
    return `${BASE_URL}/api/documents/${documentId}/page/${pageNumber}/full`;
  },
};

export { BASE_URL };
