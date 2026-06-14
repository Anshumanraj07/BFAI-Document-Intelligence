'use client';

import { motion } from 'framer-motion';
import { FileText, ExternalLink } from 'lucide-react';
import type { Citation as CitationType } from '@/types/chat';
import { documentsApi } from '@/lib/api';

interface CitationProps {
  citation: CitationType;
  onClick: () => void;
}

export default function Citation({ citation, onClick }: CitationProps) {
  const thumbnailUrl = documentsApi.getThumbnailUrl(citation.doc || citation.document_name || '', citation.page);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-3 p-2 rounded-lg bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer transition-colors group"
      onClick={onClick}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
    >
      <div className="w-12 h-16 rounded overflow-hidden border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-900 flex-shrink-0">
        <img
          src={thumbnailUrl}
          alt={`${citation.doc || citation.document_name || 'Document'} - Page ${citation.page}`}
          className="w-full h-full object-cover"
          onError={(e) => {
            (e.target as HTMLImageElement).src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="48" height="64" viewBox="0 0 48 64"><rect fill="%23f3f4f6" width="48" height="64"/><text x="24" y="32" text-anchor="middle" fill="%239ca3af" font-size="8">PDF</text></svg>';
          }}
        />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <FileText className="w-4 h-4 text-blue-500 dark:text-blue-400 flex-shrink-0" />
          <span className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
            {citation.doc || citation.document_name || 'Unknown Document'}
          </span>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
          Page {citation.page}
        </p>
      </div>
      <ExternalLink className="w-4 h-4 text-gray-400 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors" />
    </motion.div>
  );
}
