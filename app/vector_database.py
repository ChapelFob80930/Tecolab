from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv
from .config import settings
from functools import lru_cache
from .config import settings

load_dotenv()



index_name = settings.index_name

namespace_name = settings.namespace_name

@lru_cache
def get_pinecone_client():
    return Pinecone(api_key=settings.pinecone_api_key)

def get_vector_db():
    pc = get_pinecone_client()

    if not pc.has_index(index_name):
        pc.create_index_for_model(
            name=index_name,
            cloud="aws",
            region="us-east-1",
            embed={
                "model": "llama-text-embed-v2",
                "field_map": {"text": "chunk_text"}
            }
        )

    yield pc

    
    


