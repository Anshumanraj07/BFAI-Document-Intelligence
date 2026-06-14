import google.generativeai as genai

genai.configure(api_key="TUMHARI_API_KEY")

response = genai.embed_content(
    model="gemini-embedding-001",
    content="Hello world",
    task_type="retrieval_document"
)

print(response)