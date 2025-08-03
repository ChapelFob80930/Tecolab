from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, UUID, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from supabase import Base #NOTE: Change to .supabase later
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.sql.expression import text
from sqlalchemy import Enum as SqlEnum
import enum
import uuid
from pgvector.sqlalchemy import VECTOR

class AgentMemory(Base):
    __tablename__ = "agent_memory"


    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    course_id = Column(Integer, nullable=False)
    
    course_outline = Column(Text, nullable=True)
    course_outline_embeddings = Column(VECTOR, nullable=True)
    
    course_content = Column(Text, nullable=True)
    course_content_embeddings = Column(VECTOR, nullable=True)
    
    final_course = Column(Text, nullable=True)
    final_course_outline = Column(Text, nullable=True)
    final_course_outline_embeddings = Column(VECTOR, nullable=True)