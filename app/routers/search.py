from fastapi import APIRouter, Depends
from .. import schemas
from ..vector_database import get_vector_db, namespace_name
from typing import List
# from sentence_transformers import CrossEncoder
import ast
from ..config import settings

router = APIRouter(prefix = "/search",tags = ['semantic-search-vectorDB'])



@router.get("/", response_model = List[dict])
def semantic_search(query: schemas.Query, pc = Depends(get_vector_db)):

    dense_index = pc.Index(host=settings.pinecone_dense_index_host)

    ranked_results = dense_index.search(
    namespace=namespace_name, 
    query={
        "inputs": {"text": str(query)}, 
        "top_k": 20
    },
    rerank={
        "model": "bge-reranker-v2-m3",
        "top_n": 5,
        "rank_fields": ["chunk_text"]
    },
    fields=["chunk_text"]
)
    print(type(ranked_results.result.hits))

    print(ranked_results.result.hits)
    
    final_results = []
    for hit in ranked_results.result.hits:
        parsed_chunk = ast.literal_eval(hit['fields']['chunk_text'])  # Safely parse string dict
        # parsed_chunk = json.loads(hit['fields']['chunk_text'])
        parsed_chunk.update({
            "id": hit['_id'],
            "score": hit['_score']
        })
        final_results.append(parsed_chunk)

    return final_results
    
