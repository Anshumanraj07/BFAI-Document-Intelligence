import './globals.css';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import Navbar from '@/components/Navbar';


const inter = Inter({ subsets: ['latin'] });


export const metadata: Metadata = {
  title: 'Document Intelligence + Agentic RAG',
  description: 'End-to-end document intelligence system that parses messy real-world documents (scanned PDFs, handwritten pages, image-heavy reports, tables) and powers a grounded chatbot with inline citations + page thumbnails. Features: Multi-format parser, LLM-based classification, Agentic RAG with hallucination guard, Inline citations + clickable page thumbnails, Bulk upload with real-time status, Security across upload, storage, processing, retrieval. Tech Stack: Next.js 14 + FastAPI + PostgreSQL + Qdrant + Groq + Gemini 2.5 Flash', }


export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} antialiased`}>
        <Navbar />
        <main className="pt-16">{children}</main>
      </body>
    </html>
  );
}