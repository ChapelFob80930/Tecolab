from sqlalchemy import Integer, String, Text, func
from app.repository.supabase import Base #NOTE: Change to .supabase later
from sqlalchemy.sql.sqltypes import TIMESTAMP
from pgvector.sqlalchemy import VECTOR
from sqlalchemy import Column

from sqlalchemy import UniqueConstraint

class AgentMemory(Base):
    __tablename__ = "agent_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    course_id = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    course_outline = Column(Text, nullable=True)
    course_outline_embeddings = Column(VECTOR(1536), nullable=True)

    course_content = Column(Text, nullable=True)
    course_content_embeddings = Column(VECTOR(1536), nullable=True)

    final_course = Column(Text, nullable=True)
    final_course_outline = Column(Text, nullable=True)
    final_course_outline_embeddings = Column(VECTOR(1536), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_agent_memory_user_course"),
    )

# class AgentMemory(Base):
#     __tablename__ = "agent_memory"
#
#
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     user_id = Column(Integer, nullable=False)
#     created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
#
#     course_id = Column(Integer, nullable=False)
#
#     course_outline = Column(Text, nullable=True)
#     course_outline_embeddings = Column(VECTOR, nullable=True)
#
#     course_content = Column(Text, nullable=True)
#     course_content_embeddings = Column(VECTOR, nullable=True)
#
#     final_course = Column(Text, nullable=True)
#     final_course_outline = Column(Text, nullable=True)
#     final_course_outline_embeddings = Column(VECTOR, nullable=True)
#
#
#
#
# class AgentThread(Base):
#     __tablename__ = "agent_threads"
#
#     thread_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
#     course_id = Column(UUID(as_uuid=True), nullable=False)
#     state = Column(JSONB, nullable=False, default={})
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

