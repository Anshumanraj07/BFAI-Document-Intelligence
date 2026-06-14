# Document Intelligence Frontend

Next.js 14 + TypeScript frontend for Document Intelligence + Agentic RAG system.

## Features

- Chatbot with inline citations + page thumbnails
- Bulk document upload with real-time status
- Multi-turn conversation history
- Clean UI with Tailwind CSS

## Setup

```bash
npm install
npm run dev
```

Frontend runs on: `http://localhost:3000`

## Pages

- `/` - Homepage
- `/chat` - Chatbot interface
- `/upload` - Bulk upload

## API Integration

Connects to backend at: `http://localhost:8000/api`

## Build

```bash
npm run build
```

## Deploy

```bash
vercel deploy --prod
```