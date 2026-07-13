from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, UUID, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .database import Base
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.sql.expression import text
from sqlalchemy import Enum as SqlEnum
import enum
import uuid


class RoleEnum(str, enum.Enum):
    admin = "admin"
    user = "user"

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, nullable=False, server_default=text("'user_' || gen_random_uuid()::text"))
    email = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    is_active = Column(Boolean, nullable=False, server_default=text('true'))
    skills = Column(String, nullable=True)
    goal = Column(String, nullable=True)
    experience = Column(String, nullable=True)
    wants_to_learn = Column(String, nullable=True)
    role = Column(SqlEnum(RoleEnum), nullable=False, server_default="user")
