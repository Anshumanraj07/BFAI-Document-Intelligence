"""
Agentic RAG chatbot.

Pipeline:
  1. Optionally rewrite the query for better retrieval (agentic step 1).
  2. Retrieve top-k context chunks from the vector store.
  3. Build a grounded prompt with strict citation rules.
  4. Call the LLM (Gemini 1.5 Flash) to synthesize the answer.
  5. Run the hallucination guard; rewrite to "I don't know" if needed.
  6. Return answer + structured citations for the UI.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings
from app.models.schemas import Citation
from app.rag.hallucination_guard import HallucinationGuard
from app.rag.retriever import Retriever
from app.services.embedding import EmbeddingService
from app.utils.helpers import truncate_text
from app.utils.logger import get_logger

logger = get_logger(__name__)


CHATBOT_SYSTEM_PROMPT = '''
Answer this question in DETAIL using the provided context and conversation history.

IMPORTANT RULES:
1. Answer must be LONG and DETAILED (at least 200-300 words)
2. Include information from ALL retrieved chunks/documents
3. For follow-up questions (like "explain why", "how", "tell me more", "what do you mean"):
   - CRITICAL: Use the PREVIOUS conversation to understand context
   - Infer from RELATED information in the documents
   - Connect dots between different chunks and previous answers
   - If user asks "why" or "explain", reference the previous claim and provide supporting evidence
4. Add inline citations for EVERY claim: [document_name.pdf, Page X]
5. Be thorough and comprehensive

FOLLOW-UP QUESTION HANDLING:
- When user asks "explain why" or "how do you know", look at your previous answer and find the specific claims made
- Use the conversation history to understand what the user is referring to
- Provide detailed explanations based on the evidence in the documents
- Connect information across multiple document chunks to build a complete picture
- Be flexible in interpreting questions - use context to clarify ambiguous references

IF CONTEXT IS LIMITED:
- Say: "Based on the available information in the documents..."
- Infer from related sections
- Connect multiple chunks together
- Use conversation history to fill gaps
- ONLY say "I don't know" if completely nothing relevant can be found

Question: {question}

Context (from retrieved documents):
{context}

Previous conversation (for follow-up context):
{history}

Provide a DETAILED, COMPREHENSIVE answer:
'''


class ChatbotError(Exception):
    """Raised when the chatbot pipeline fails irrecoverably."""
    pass


class Chatbot:
    """Orchestrates retrieval + grounded generation."""

    def __init__(
        self,
        retriever: Retriever,
        embedding_service: EmbeddingService,
        guard: Optional[HallucinationGuard] = None,
    ) -> None:
        self.retriever = retriever
        self.embeddings = embedding_service
        self.guard = guard or HallucinationGuard()
        self._timeout = 30.0

    # ============================================================
    # Public entry point
    # ============================================================
    async def ask(
        self,
        *,
        question: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 10,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Answer `question` using RAG over `document_ids` (or all docs).

        Returns a dict with: `answer`, `citations`, `used_documents`,
        `confidence`, `needs_more_info`.
        """
        if not question or not question.strip():
            raise ChatbotError("Empty question")

        # --- Step 1: agentic query rewrite (lightweight) ---
        rewritten = await self._rewrite_query(question, chat_history or [])

        # --- Step 2: retrieve ---
        hits = await self.retriever.retrieve(
            rewritten,
            top_k=top_k,
            document_ids=document_ids,
        )

        if not hits:
            answer = self.guard.dont_know_message()
            return {
                "answer": answer,
                "citations": [],
                "used_documents": [],
                "confidence": 0.0,
                "needs_more_info": True,
            }

        # --- Step 3: format context + build prompt ---
        context_str = self.retriever.format_context(hits)
        prompt = self._build_prompt(question, context_str, chat_history or [])

        # --- Step 4: generate ---
        raw_answer = await self._call_gemini(prompt)

        # --- Step 5: guard ---
        top_score = hits[0].get("score", 0.0) if hits else 0.0
        guard_result = self.guard.check(raw_answer, hits, top_score=top_score)

        if not guard_result.is_valid:
            logger.info("Guard rejected answer: %s", guard_result.reason)
            answer = self.guard.dont_know_message()
        else:
            answer = raw_answer.strip()

        # --- Step 6: build citations ---
        citations = self._build_citations(hits, answer)
        used_documents = list({
            c.document_name for c in citations
        })

        return {
            "answer": answer,
            "citations": citations,
            "used_documents": used_documents,
            "confidence": guard_result.confidence,
            "needs_more_info": guard_result.needs_more_info,
        }

    # ============================================================
    # Agentic query rewrite
    # ============================================================
    async def _rewrite_query(
        self,
        question: str,
        history: List[Dict[str, str]],
    ) -> str:
        """
        Rewrite follow-up questions into self-contained queries
        so retrieval has enough context.
        """

        if not history:
            return question

        question_lower = question.lower()

        follow_up_phrases = [
            "why",
            "explain",
            "how",
            "what do you mean",
            "tell me more",
            "elaborate",
            "can you explain",
            "why do you say that",
            "how do you know",
            "what makes you think",
        ]

        is_followup = (
            len(question.split()) <= 15
            or any(p in question_lower for p in follow_up_phrases)
        )

        if not is_followup:
            return question

        last_user = None
        last_assistant = None

        for msg in reversed(history):
            if msg.get("role") == "assistant" and not last_assistant:
                last_assistant = msg.get("content", "")
            elif msg.get("role") == "user" and not last_user:
                last_user = msg.get("content", "")

            if last_user and last_assistant:
                break

        if last_user:
            rewritten = (
                f"Original question: {last_user}\n"
                f"Previous answer: {last_assistant or ''}\n"
                f"Follow-up question: {question}"
            )
            return rewritten

        return question

    # ============================================================
    # Prompt construction
    # ============================================================
    def _build_prompt(
        self,
        question: str,
        context_str: str,
        history: List[Dict[str, str]],
    ) -> str:
        history_str = ""
        if history:
            history_str = "\n\nCHAT HISTORY:\n"
            for m in history[-6:]:  # keep last 6 turns
                role = m.get("role", "user").upper()
                content = truncate_text(m.get("content", ""), 500)
                history_str += f"{role}: {content}\n"

        return CHATBOT_SYSTEM_PROMPT.format(
            question=question,
            context=context_str,
            history=history_str
        )

    # ============================================================
    # LLM call (Gemini 1.5 Flash)
    # ============================================================
    async def _call_gemini(self, prompt: str) -> str:
        if not settings.GEMINI_API_KEY or "your-" in settings.GEMINI_API_KEY:
            logger.warning("Gemini not configured — returning canned response")
            return self.guard.dont_know_message()

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2000,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:
            logger.exception("Gemini call failed: %s", exc)
            raise ChatbotError(f"LLM call failed: {exc}") from exc

    # ============================================================
    # Citation building
    # ============================================================
    def _build_citations(
        self,
        hits: List[Dict[str, Any]],
        answer: str,
        max_citations: int = 5,
    ) -> List[Citation]:
        """Convert the top retrieval hits into Citation objects."""
        out: List[Citation] = []
        for h in hits[:max_citations]:
            payload = h.get("payload", {}) or {}
            out.append(Citation(
                document_id=payload.get("document_id", ""),
                document_name=payload.get("document_name", "Unknown"),
                page_number=int(payload.get("page_number", 0) or 0),
                chunk_text=truncate_text(payload.get("chunk_text", ""), 300),
                thumbnail_url=payload.get("image_url") or None,
                score=float(h.get("score", 0.0)),
            ))
        return out
