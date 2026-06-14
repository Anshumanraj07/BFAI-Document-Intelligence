'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { X, ZoomIn, ZoomOut } from 'lucide-react';
import { useState } from 'react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  imageUrl: string;
  documentName: string;
  pageNumber: number;
}

export default function Modal({ isOpen, onClose, imageUrl, documentName, pageNumber }: ModalProps) {
  const [zoom, setZoom] = useState(1);

  const toggleZoom = () => {
    setZoom(zoom === 1 ? 2 : 1);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            transition={{ type: 'spring', damping: 25 }}
            className="relative max-w-4xl max-h-[90vh] rounded-xl overflow-hidden bg-white dark:bg-gray-900 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{documentName}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">Page {pageNumber}</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={toggleZoom}
                  className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                >
                  {zoom === 1 ? <ZoomIn className="w-5 h-5 text-gray-600 dark:text-gray-300" /> : <ZoomOut className="w-5 h-5 text-gray-600 dark:text-gray-300" />}
                </button>
                <button
                  onClick={onClose}
                  className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                >
                  <X className="w-5 h-5 text-gray-600 dark:text-gray-300" />
                </button>
              </div>
            </div>
            <div className="overflow-auto p-4 max-h-[calc(90vh-80px)]">
              <motion.img
                src={imageUrl}
                alt={`${documentName} - Page ${pageNumber}`}
                className="mx-auto rounded-lg shadow-lg"
                animate={{ scale: zoom }}
                transition={{ type: 'spring', stiffness: 300 }}
              />
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
