# Document Intelligence + Agentic RAG

End-to-end document intelligence system that parses messy real-world documents (scanned PDFs, handwritten pages, image-heavy reports, tables) and powers a grounded chatbot with inline citations + page thumbnails.

## Features

- Multi-format document parser (PDFs, scanned pages, tables)
- LLM-based classification with structured JSON output
- Agentic RAG chatbot with hallucination guard
- Inline citations with document name + page number
- Clickable page thumbnails in UI
- Bulk upload with real-time processing status
- Security across upload, storage, processing, retrieval layers

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14 + TypeScript |
| Backend | FastAPI + Python 3.12 |
| Database | SQLite (metadata) |
| Vector DB | Qdrant (embeddings) |
| LLM (Classification) | Groq (Llama 3.3) |
| LLM (Generation) | Gemini 2.5 Flash |
| OCR | Tesseract (fallback) |

## Setup

### 1. Clone Repository

```bash
git clone <your-repo-url>
cd BFAI
```

### 2. Install Dependencies

```bash
# Frontend
cd frontend
npm install

# Backend
cd backend
pip install -r requirements.txt
```

### 3. Configure API Keys

```bash
# Backend: Create .env file
cd backend
touch .env

# Add API keys:
API_KEY=test-key-12345-make-this-long-and-random-in-production
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_qdrant_api_key_here
```

### 4. Start Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Backend runs on: `http://localhost:8000`

API docs: `http://localhost:8000/api/docs`

### 5. Start Frontend

```bash
cd frontend
npm run dev
```

Frontend runs on: `http://localhost:3000`

## Usage

### Upload Documents

1. Open: `http://localhost:3000/upload`
2. Click "Choose PDF file" or drag-drop
3. Select PDF document
4. Click "Upload"
5. Wait for processing status: parsing → classifying → indexed

### Chat with Documents

1. Open: `http://localhost:3000/chat`
2. Type question (e.g., "What is the main objective?")
3. Click "Send"
4. View answer with inline citations
5. Click citation thumbnail to view full page

### Example Questions

- "What is the main objective of this assessment?"
- "Compare both uploaded documents"
- "What skills are mentioned in the resume?"
- "What is the financial performance on page 3?"

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload` | POST | Upload documents |
| `/api/documents` | GET | List all documents |
| `/api/documents/{id}` | GET | Get document metadata |
| `/api/documents/{id}/pages` | GET | Get page thumbnails |
| `/api/chat` | POST | Ask question to RAG |
| `/api/chat/history` | GET | Get chat history |
| `/api/status/{id}` | GET | Get processing status |

## Architecture
Frontend (Next.js)
↓
API Gateway (JWT Auth + Rate Limiting)
↓
Backend (FastAPI)
↓
Document Parser (pdfplumber + OCR)
↓
Classification (Groq LLM)
↓
Chunking + Embeddings (BAAI/bge-small)
↓
Vector Store (Qdrant)
↓
Retrieval (top_k=10)
↓
Answer Generation (Gemini 2.5 Flash)
↓
Citation Verification + Hallucination Guard
↓
Frontend (Show answer + citations + thumbnails)

text

## Security Decisions

### What I Implemented

1. **API Authentication**
   - JWT token validation on all endpoints
   - X-API-Key header required for uploads/chat

2. **File Validation**
   - PDF file type only (no EXE, scripts)
   - Max file size: 10MB
   - Filename sanitization (remove special chars)

3. **Rate Limiting**
   - 60 requests/minute per IP
   - Separate limits for upload (10/min) and chat (30/min)

4. **Input Sanitization**
   - SQL injection prevention (parameterized queries)
   - XSS prevention (HTML escaping in frontend)

5. **Storage Security**
   - Files stored outside public web root
   - Internal-only file paths (no direct URL access)

### What I Considered But Skipped

1. **Encryption at Rest**
   - Skipped: Complex to implement in 3 days
   - Would add: AES-256 encryption for sensitive documents

2. **OAuth2 / SSO**
   - Skipped: Overkill for demo
   - Would add: Auth0 integration for enterprise users

3. **Audit Logging**
   - Skipped: No logging infrastructure
   - Would add: Log all document access + chat queries

4. **Data Retention Policies**
   - Skipped: No auto-deletion
   - Would add: Auto-delete documents after 30 days

### What I Would Add With More Time

1. **Multi-Tenant Support**
   - User-specific document isolation
   - Role-based access control (RBAC)

2. **Compliance (GDPR, HIPAA)**
   - Data privacy compliance
   - Right to deletion

3. **Advanced Threat Detection**
   - Malware scanning for uploaded files
   - Anomaly detection for API usage

4. **Zero-Knowledge Architecture**
   - End-to-end encryption
   - Server cannot read document content

## Project Structure
BFAI/
├── frontend/
│ ├── app/
│ │ ├── chat/
│ │ │ └── page.tsx # Chatbot UI
│ │ ├── upload/
│ │ │ └── page.tsx # Bulk upload UI
│ │ ├── components/
│ │ │ ├── ChatBox.tsx
│ │ │ ├── CitationCard.tsx
│ │ │ └── ThumbnailViewer.tsx
│ │ ├── layout.tsx
│ │ └── page.tsx # Homepage
│ ├── package.json
│ └── tsconfig.json
├── backend/
│ ├── app/
│ │ ├── api/
│ │ │ ├── upload.py # Upload endpoints
│ │ │ ├── chat.py # Chat endpoints
│ │ │ └── documents.py # Document endpoints
│ │ ├── rag/
│ │ │ ├── retriever.py # Vector search
│ │ │ ├── chatbot.py # Answer generation
│ │ │ └── prompts.py # LLM prompts
│ │ ├── parsers/
│ │ │ ├── pdf_parser.py # PDF parsing
│ │ │ └── ocr.py # OCR fallback
│ │ ├── classifiers/
│ │ │ └── document_classifier.py # LLM classification
│ │ ├── services/
│ │ │ ├── storage.py # File storage
│ │ │ └── qdrant_service.py # Vector DB
│ │ ├── models/
│ │ │ ├── document.py
│ │ │ └── chat.py
│ │ ├── config.py
│ │ └── main.py # FastAPI app
│ ├── requirements.txt
│ └── .env
├── sample_documents/
│ └── BFAI_AI_Engineer_Assessment.pdf
├── README.md
└── .gitignore

text

## Sample Documents

Included in `sample_documents/`:

1. `BFAI_AI_Engineer_Assessment.pdf` - Assessment PDF (2 pages)

Chatbot works immediately on first run with this document.

## Testing

### API Test

```bash
# Start backend first:
cd backend
uvicorn app.main:app --reload --port 8000

# Run test:
python test_api.py
```

Expected output:
✅ Backend running: Status 200
✅ POST /api/upload: WORKS
✅ GET /api/documents: WORKS
✅ POST /api/chat: WORKS
✅ GET /api/status/{id}: WORKS
✅ GET /api/documents/{id}/pages: WORKS
🎉 ALL API ENDPOINTS WORKING!

text

## Deployment

### Frontend (Vercel)

```bash
# 1. Push to GitHub
git add .
git commit -m "Deploy ready"
git push

# 2. Deploy to Vercel
vercel deploy --prod

# OR: Connect GitHub repo to Vercel for auto-deploy
```

### Backend (Render)

```bash
# 1. Create Render account
# 2. Create new Web Service
# 3. Connect GitHub repo
# 4. Set build command: pip install -r requirements.txt
# 5. Set start command: uvicorn app.main:app --host 0.0.0.0 --port 8000
# 6. Add environment variables (API_KEY, GROQ_API_KEY, etc.)
```

## Limitations

1. **OCR Quality**: Handwritten pages may have low OCR accuracy
2. **Table Extraction**: Complex tables may lose structure
3. **Vector Store**: Using in-memory fallback (Qdrant not configured)
4. **Sample Documents**: Only 1 PDF included (need 5 for full assessment)
5. **Voice Input**: Not implemented (bonus feature)

## Future Enhancements

1. Multi-agent architecture (Planning + Tool Calling + Verification agents)
2. Redis caching for faster retrieval
3. PostgreSQL database (replace SQLite)
4. Qdrant Cloud (production vector store)
5. OCR improvements (pdf2image + pytesseract pipeline)
6. Table structure preservation
7. Voice input with speech-to-text API
8. A/B testing framework
9. LangSmith tracing for observability
10. Ragas evaluation for quality metrics

## License

MIT License

## Contact

Anshuman Raj - anshumanraj2207@gmail.com

---

**Built for BFAI AI Engineer Assessment**