import google.generativeai as genai
from app.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

result = genai.embed_content(
    model="gemini-embedding-001",
    content="Hello world",
    task_type="retrieval_document"
)

print(result)