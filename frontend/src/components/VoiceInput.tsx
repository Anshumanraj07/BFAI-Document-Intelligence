'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff } from 'lucide-react';

interface VoiceInputProps {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}

export default function VoiceInput({ onTranscript, disabled = false }: VoiceInputProps) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [isSupported, setIsSupported] = useState(true);
  const [recognition, setRecognition] = useState<{ start: () => void; stop: () => void } | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const SpeechRecognitionAPI = (window as { SpeechRecognition?: new () => { start: () => void; stop: () => void }; webkitSpeechRecognition?: new () => { start: () => void; stop: () => void } }).SpeechRecognition || (window as { webkitSpeechRecognition?: new () => { start: () => void; stop: () => void } }).webkitSpeechRecognition;
      if (SpeechRecognitionAPI) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const recognitionInstance = new SpeechRecognitionAPI() as any;
        recognitionInstance.continuous = true;
        recognitionInstance.interimResults = true;
        recognitionInstance.lang = 'en-US';

        recognitionInstance.onresult = (event: { resultIndex: number; results: { isFinal: boolean; [index: number]: { transcript: string } }[] }) => {
          let finalTranscript = '';
          let interimTranscript = '';

          for (let i = event.resultIndex; i < event.results.length; i++) {
            const result = event.results[i];
            if (result.isFinal) {
              finalTranscript += result[0].transcript;
            } else {
              interimTranscript += result[0].transcript;
            }
          }

          setTranscript(finalTranscript || interimTranscript);
        };

        recognitionInstance.onend = () => {
          setIsListening(false);
          if (transcript.trim()) {
            onTranscript(transcript.trim());
            setTranscript('');
          }
        };

        recognitionInstance.onerror = (event: { error: string }) => {
          console.error('Speech recognition error:', event.error);
          setIsListening(false);
        };

        setRecognition(recognitionInstance);
      } else {
        setIsSupported(false);
      }
    }
  }, []);

  useEffect(() => {
    if (transcript.trim() && !isListening) {
      onTranscript(transcript.trim());
      setTranscript('');
    }
  }, [transcript, isListening, onTranscript]);

  const toggleListening = useCallback(() => {
    if (!recognition || disabled) return;

    if (isListening) {
      recognition.stop();
      setIsListening(false);
    } else {
      setTranscript('');
      recognition.start();
      setIsListening(true);
    }
  }, [recognition, isListening, disabled]);

  if (!isSupported) {
    return null;
  }

  return (
    <div className="relative">
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={toggleListening}
        disabled={disabled}
        className={`p-2 rounded-full transition-colors ${
          isListening
            ? 'bg-red-500 text-white'
            : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        {isListening ? (
          <MicOff className="w-5 h-5" />
        ) : (
          <Mic className="w-5 h-5" />
        )}
      </motion.button>

      {/* Recording indicator */}
      <AnimatePresence>
        {isListening && (
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 text-sm rounded-lg whitespace-nowrap shadow-lg"
          >
            <div className="flex items-center gap-2">
              <motion.div
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ repeat: Infinity, duration: 1 }}
                className="w-2 h-2 bg-red-500 rounded-full"
              />
              Listening...
            </div>
            {transcript && (
              <p className="mt-1 text-xs text-gray-300 dark:text-gray-600 max-w-xs truncate">
                {transcript}
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
