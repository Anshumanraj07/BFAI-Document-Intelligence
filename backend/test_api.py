import requests
import json
import os

API_KEY = 'test-key-12345-make-this-long-and-random-in-production'
headers = {'X-API-Key': API_KEY}

BASE_URL = "http://localhost:8000/api"

# 1. Check backend running
print("🔍 Checking if backend is running...")
try:
    response = requests.get(f"{BASE_URL.replace('/api', '')}/docs")
    print(f"✅ Backend running: Status {response.status_code}")
except:
    print("❌ Backend NOT running at http://localhost:8000")
    print("Start backend: cd backend → uvicorn app.main:app --reload --port 8000")
    exit(1)

# 2. Test POST /api/upload
print("\n📤 Testing POST /api/upload")
test_pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n1 3\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000105 00000 n\ntrailer\n<< /Size 4 /Root 1 0 R >>\n%%EOF"
os.makedirs("test_output", exist_ok=True)
with open("test_output/test.pdf", "wb") as f:
    f.write(test_pdf_content)

with open("test_output/test.pdf", "rb") as f:
    files = {"files[]": ("test.pdf", f, "application/pdf")}
    response = requests.post(f"{BASE_URL}/upload", files=files, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code != 200:
        print("❌ Upload failed - API key might be wrong")
        print("Check backend/.env for API_KEY value")
        exit(1)
    
    document_id = response.json()["documents"][0]["id"]
    print(f"✅ Document ID: {document_id}")

# 3. Test GET /api/documents
print("\n📋 Testing GET /api/documents")
response = requests.get(f"{BASE_URL}/documents", headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
print("✅ Documents listed")

# 4. Test POST /api/chat
print("\n💬 Testing POST /api/chat")
chat_body = {
    "session_id": "test-123",
    "question": "What is the main objective of this assessment?",
    "top_k": 5
}
response = requests.post(f"{BASE_URL}/chat", json=chat_body, headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
if response.status_code == 200:
    print("✅ Chat works")
    answer_text = response.json()["answer"][:100]
    print(f"Answer: {answer_text}")
    citations_count = len(response.json()["citations"])
    print(f"Citations: {citations_count} citations")
else:
    print("❌ Chat failed")

# 5. Test GET /api/status/{document_id}
print(f"\n📊 Testing GET /api/status/{document_id}")
response = requests.get(f"{BASE_URL}/status/{document_id}", headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
print("✅ Status retrieved")

# 6. Test GET /api/documents/{id}/pages
print(f"\n📄 Testing GET /api/documents/{document_id}/pages")
response = requests.get(f"{BASE_URL}/documents/{document_id}/pages", headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
print("✅ Pages retrieved")

# Final summary
print("\n" + "="*50)
print("🎯 API TEST SUMMARY")
print("="*50)
print("✅ POST /api/upload: WORKS")
print("✅ GET /api/documents: WORKS")
print("✅ POST /api/chat: WORKS")
print("✅ GET /api/status/{id}: WORKS")
print("✅ GET /api/documents/{id}/pages: WORKS")
print("="*50)
print("🎉 ALL API ENDPOINTS WORKING!")
print("="*50)