# BFAI Document Intelligence — Backend

A production-ready FastAPI backend implementing a **Document Parser + LLM Classifier + Agentic RAG Chatbot** pipeline. Built for the "Build Fast with AI" (BFAI) AI Engineer Intern assessment.

---

## 🎯 Features

- 📄 **Multi-format Document Parsing** (PDF, images, TXT) with `pdfplumber` + `pdf2image` + `pytesseract`
- ✍️ **Handwritten OCR** and structured **Table Extraction**
- 🤖 **LLM-based Classification** (Groq Llama 3) returning strict JSON schema
- 🔍 **Agentic RAG Chatbot** (Gemini 1.5 Flash) with inline citations
- 🛡️ **Hallucination Guard** with "I don't know" enforcement
- 🔐 **4-Layer Security** (file validation, API key auth, PII redaction, CORS)
- 📦 **Bulk Upload** with async background processing
- 🎙️ **Voice Input** endpoint (Groq Whisper STT)
- 🚦 **Rate Limiting** via `slowapi`

---

## 🏗️ Architecture

```
Client (Next.js)  →  FastAPI  →  Background Worker  →  Parsers  →  Classifier  →  Vector DB
                ←  Chat API  ←  Agentic RAG        ←  Retriever ←  LLM
```

See `/docs/architecture.md` in the repo root for the full diagram.

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- Python **3.11+**
- `tesseract-ocr` system package
- `poppler-utils` (for `pdf2image`)

```bash
# macOS
brew install tesseract poppler

# Ubuntu/Debian
sudo apt-get install tesseract-ocr poppler-utils libmagic1
```

### 2. Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env with your real API keys
```

### 3. Run
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API will be live at:
- **Swagger Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health

---

## 🐳 Docker

```bash
docker build -t bfai-backend .
docker run --env-file .env -p 8000:8000 bfai-backend
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET`  | `/health` | Health check |
| `POST` | `/api/upload` | Upload a single file |
| `POST` | `/api/upload-bulk` | Upload multiple files |
| `GET`  | `/api/upload/{job_id}/status` | Get processing status |
| `POST` | `/api/classify` | Re-classify a document |
| `POST` | `/api/chat` | Multi-turn chat with RAG |
| `GET`  | `/api/documents` | List all documents |
| `GET`  | `/api/documents/{id}` | Get document details |
| `GET`  | `/api/documents/{id}/page/{n}/thumbnail` | Get page thumbnail |
| `GET`  | `/api/documents/{id}/page/{n}/full` | Get full page image |
| `POST` | `/api/voice/transcribe` | Transcribe audio to text |

All endpoints (except `/health`) require the `X-API-Key` header.

---

## 🧪 Testing

```bash
pytest -v
pytest --cov=app tests/
```

---

## 🔐 Security Decisions

| Layer | Implementation |
|---|---|
| **Upload** | Extension + size + magic number validation via `app/security/file_validation.py` |
| **Storage** | UUID-only filenames; immediate cleanup of temp files |
| **Processing** | All API keys in `.env`; Pydantic strict validation against prompt injection |
| **API/Retrieval** | CORS whitelisting; static API key auth; rate limiting (60 req/min); strict prompt grounding |

> **Out of scope for MVP:** ClamAV malware scanning, RBAC, OAuth, at-rest encryption (relying on cloud provider defaults).

---

## 🌍 Environment Variables

See [`.env.example`](./.env.example) for the full list. All variables are validated by `app/config.py` (Pydantic Settings).

---

## 📂 Project Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI app entrypoint
│   ├── config.py               # Settings & env validation
│   ├── parsers/                # OCR & text extraction
│   ├── classifiers/            # LLM-based document classification
│   ├── rag/                    # Vector store, retriever, chatbot
│   ├── api/                    # HTTP route handlers
│   ├── security/               # Validation, auth, PII filter
│   ├── models/                 # Pydantic & SQLAlchemy models
│   ├── services/               # Business logic (storage, embeddings, pipeline)
│   ├── utils/                  # Logger & helpers
│   └── tests/                  # Pytest suite
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

---

## 📝 License

MIT — for BFAI assessment purposes.
