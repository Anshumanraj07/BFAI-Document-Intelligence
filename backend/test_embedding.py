import asyncio
from app.services.embedding import EmbeddingService

async def test():
    emb = EmbeddingService()
    result = await emb.embed_query('test')
    print(f'Embedding length: {len(result)}')
    print(f'First 5 values: {result[:5]}')

if __name__ == "__main__":
    asyncio.run(test())