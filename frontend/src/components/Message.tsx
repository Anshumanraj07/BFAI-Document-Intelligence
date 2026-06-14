'use client';

import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { User, Bot } from 'lucide-react';
import type { Message as MessageType, Citation as CitationType } from '@/types/chat';
import Citation from './Citation';

interface MessageProps {
  message: MessageType;
  onCitationClick: (citation: CitationType) => void;
}

export default function Message({ message, onCitationClick }: MessageProps) {
  const isUser = message.role === 'user';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      {/* Avatar */}
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser
            ? 'bg-blue-500 text-white'
            : 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
        }`}
      >
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>

      {/* Message Content */}
      <div
        className={`max-w-[70%] ${isUser ? 'bg-blue-500 text-white' : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100'} rounded-2xl px-4 py-3 shadow-sm border ${
          isUser ? 'border-blue-500' : 'border-gray-200 dark:border-gray-700'
        }`}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown
              components={{
                p: ({ children }) => <p className="mb-2 last:mb-0 text-sm">{children}</p>,
                ul: ({ children }) => <ul className="list-disc pl-4 mb-2 text-sm">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 text-sm">{children}</ol>,
                code: ({ children }) => (
                  <code className="bg-gray-100 dark:bg-gray-900 px-1 py-0.5 rounded text-sm">
                    {children}
                  </code>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
              Sources
            </p>
            <div className="flex flex-wrap gap-2">
              {message.citations.map((citation, index) => (
                <Citation
                  key={`${citation.doc || citation.document_name || 'unknown'}-${citation.page}-${index}`}
                  citation={citation}
                  onClick={() => onCitationClick(citation)}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}
