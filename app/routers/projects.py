from fastapi import APIRouter, Depends, status
from .. import schemas
from ..vector_database import get_vector_db, namespace_name
from uuid import uuid4
from ..config import settings

router = APIRouter(prefix = "/projects", tags = ['manage-show-projects-vectorDB'])

@router.get("/")
def get_all_projects(): #not implemented yet
    pass

#implementing create to maintain my understanding while creating logic fro semantic search

@router.post("/", status_code=status.HTTP_201_CREATED)
def insert_project(project: schemas.ProjectCreate, pc=Depends(get_vector_db)): #only for admin and for general courses, we won't put personalized courses in vector db, we will maintain another separate db for that. For now will write general code, once projects is done will further implement this
    dense_index = pc.Index(host=settings.pinecone_dense_index_host)
    project_id = "course_" + str(uuid4())
    print(project.pinecone_metadata(id=project_id))
    metadata = [{"id":project_id, "chunk_text":str(project.pinecone_metadata(id=project_id))}]
    # metadata = [{"id":project_id, "chunk_text":json.dumps(project.pinecone_metadata(id=project_id))}]
    dense_index.upsert_records(
        namespace_name,
        metadata
    )
    
    return {"message": "Project inserted into Pinecone", "project_id": project_id}
    