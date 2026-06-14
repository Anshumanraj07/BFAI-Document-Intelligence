'use client';

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, File, X, CheckCircle, AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import type { UploadStatus, BulkUploadResponse, ApiError } from '@/types/chat';
import { uploadApi } from '@/lib/api';

interface FileUploadState {
  file: File;
  jobId?: string;
  status?: UploadStatus;
  error?: string;
}

export default function BulkUpload() {
  const [files, setFiles] = useState<FileUploadState[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFiles = Array.from(e.dataTransfer.files).filter(
      (file) =>
        file.type === 'application/pdf' ||
        file.type === 'image/png' ||
        file.type === 'image/jpeg' ||
        file.type === 'text/plain'
    );
    const newFiles = droppedFiles.map((file) => ({ file }));
    setFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files).filter(
        (file) =>
          file.type === 'application/pdf' ||
          file.type === 'image/png' ||
          file.type === 'image/jpeg' ||
          file.type === 'text/plain'
      );
      const newFiles = selectedFiles.map((file) => ({ file }));
      setFiles((prev) => [...prev, ...newFiles]);
    }
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0 || isUploading) return;

    setIsUploading(true);

    // Reset states
    setFiles((prev) =>
      prev.map((f) => ({ ...f, status: undefined, jobId: undefined, error: undefined }))
    );

    try {
      const uploadFiles = files.map((f) => f.file);
      const response: BulkUploadResponse = await uploadApi.uploadBulk(uploadFiles);

      // Map document_ids to files by index
      setFiles((prev) =>
        prev.map((f, idx) => ({
          ...f,
          jobId: response.job_id,
          documentId: response.document_ids[idx],
        }))
      );

      // Start polling for each file
      const pollPromises = files.map(async (_, idx) => {
        try {
          await uploadApi.pollJobStatus(
            response.job_id,
            (status) => {
              setFiles((prev) =>
                prev.map((f, i) =>
                  i === idx ? { ...f, status } : f
                )
              );
            },
            2000,
            120
          );
        } catch (err) {
          const apiError = err as ApiError;
          setFiles((prev) =>
            prev.map((f, i) =>
              i === idx ? { ...f, error: apiError.message } : f
            )
          );
        }
      });

      await Promise.all(pollPromises);
    } catch (err) {
      const apiError = err as ApiError;
      setFiles((prev) =>
        prev.map((f) => ({ ...f, error: apiError.message }))
      );
    } finally {
      setIsUploading(false);
    }
  };

  const retryUpload = async (index: number) => {
    const fileState = files[index];
    if (!fileState?.file) return;

    setFiles((prev) =>
      prev.map((f, i) =>
        i === index ? { ...f, status: undefined, error: undefined } : f
      )
    );

    try {
      const response = await uploadApi.uploadSingle(fileState.file);
      setFiles((prev) =>
        prev.map((f, i) =>
          i === index ? { ...f, jobId: response.job_id, documentId: response.document_id } : f
        )
      );

      await uploadApi.pollJobStatus(response.job_id, (status) => {
        setFiles((prev) =>
          prev.map((f, i) => (i === index ? { ...f, status } : f))
        );
      });
    } catch (err) {
      const apiError = err as ApiError;
      setFiles((prev) =>
        prev.map((f, i) =>
          i === index ? { ...f, error: apiError.message } : f
        )
      );
    }
  };

  const getStatusColor = (status?: UploadStatus['status']) => {
    switch (status) {
      case 'queued':
        return 'bg-gray-400';
      case 'parsing':
        return 'bg-yellow-500';
      case 'classifying':
        return 'bg-orange-500';
      case 'indexed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      default:
        return 'bg-gray-300';
    }
  };

  const getStatusIcon = (status?: UploadStatus['status'], error?: string) => {
    if (error) return <AlertCircle className="w-5 h-5 text-red-500" />;
    switch (status) {
      case 'queued':
      case 'parsing':
      case 'classifying':
        return <Loader2 className="w-5 h-5 animate-spin text-gray-500" />;
      case 'indexed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <File className="w-5 h-5 text-gray-400" />;
    }
  };

  const getProgress = (status?: UploadStatus) => {
    if (!status) return 0;
    const { completed_files, total_files } = status;
    if (total_files === 0) return 0;
    return Math.round((completed_files / total_files) * 100);
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-900 px-4 py-8">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Bulk Document Upload
          </h1>
          <p className="text-gray-500 dark:text-gray-400">
            Upload multiple PDF, PNG, JPG, or TXT documents for parsing and indexing
          </p>
        </motion.div>

        {/* Drop Zone */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-2xl p-12 text-center transition-colors ${
            isDragging
              ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
              : 'border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800'
          }`}
        >
          <input
            type="file"
            multiple
            accept=".pdf,.png,.jpg,.jpeg,.txt"
            onChange={handleFileSelect}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            disabled={isUploading}
          />
          <Upload
            className={`w-12 h-12 mx-auto mb-4 ${
              isDragging ? 'text-blue-500' : 'text-gray-400'
            }`}
          />
          <p className="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">
            Drag and drop files here
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            or click to browse (PDF, PNG, JPG, TXT)
          </p>
        </motion.div>

        {/* Files List */}
        <AnimatePresence>
          {files.length > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-6 space-y-2"
            >
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Selected Files ({files.length})
                </h3>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleUpload}
                  disabled={isUploading}
                  className={`px-6 py-2 rounded-lg font-medium flex items-center gap-2 ${
                    isUploading
                      ? 'bg-gray-200 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
                      : 'bg-blue-500 text-white hover:bg-blue-600'
                  }`}
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload className="w-4 h-4" />
                      Upload All
                    </>
                  )}
                </motion.button>
              </div>

              {files.map((fileState, index) => (
                <motion.div
                  key={`${fileState.file.name}-${index}`}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700"
                >
                  <div className="flex items-center gap-4 mb-2">
                    <div
                      className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                        fileState.error
                          ? 'bg-red-100 dark:bg-red-900/30'
                          : fileState.status?.status === 'indexed'
                          ? 'bg-green-100 dark:bg-green-900/30'
                          : 'bg-gray-100 dark:bg-gray-700'
                      }`}
                    >
                      {getStatusIcon(fileState.status?.status, fileState.error)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                        {fileState.file.name}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {(fileState.file.size / 1024 / 1024).toFixed(2)} MB
                        {fileState.status && (
                          <span className="ml-2 capitalize text-gray-600 dark:text-gray-300">
                            • {fileState.status.status}
                          </span>
                        )}
                      </p>
                    </div>
                    {!isUploading && !fileState.status && (
                      <button
                        onClick={() => removeFile(index)}
                        className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
                      >
                        <X className="w-5 h-5 text-gray-400" />
                      </button>
                    )}
                    {fileState.error && !isUploading && (
                      <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={() => retryUpload(index)}
                        className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
                      >
                        <RefreshCw className="w-5 h-5 text-red-500" />
                      </motion.button>
                    )}
                  </div>
                  {/* Progress bar */}
                  {(fileState.status || fileState.error) && (
                    <div className="w-full h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${fileState.error ? 100 : getProgress(fileState.status)}%` }}
                        transition={{ duration: 0.5 }}
                        className={`h-full ${getStatusColor(fileState.status?.status)}`}
                      />
                    </div>
                  )}
                  {fileState.error && (
                    <p className="mt-2 text-xs text-red-500">{fileState.error}</p>
                  )}
                  {fileState.status?.current_file && fileState.status.status !== 'indexed' && (
                    <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                      Processing: {fileState.status.current_file}
                    </p>
                  )}
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
