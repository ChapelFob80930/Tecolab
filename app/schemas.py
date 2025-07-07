from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Annotated, List
from uuid import UUID

class UserBase(BaseModel):
    email: EmailStr = Field(..., description="The user's email address")
    first_name: str = Field(...,min_length=1, description="The user's first name")
    last_name: str = Field(...,min_length=1, description="The user's last name")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="The date and time when the user was created")
    
class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="The user's password")
    skills: Optional[str] = Field(None, description="The user's skills")
    goal: Optional[str] = Field(None, description="The user's goal")
    experience: Optional[str] = Field(None, description="The user's experience")
    wants_to_learn: Optional[str] = Field(None, description="What the user wants to learn")
    
class UserOut(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime
    first_name: str
    last_name: str
    skills: Optional[str] = None
    goal: Optional[str] = None
    experience: Optional[str] = None
    wants_to_learn: Optional[str] = None
    
    class Config:
        orm_mode = True
    
class Token(BaseModel):
    access_token: str
    token_type: str
    
class TokenData(BaseModel):
    id: Optional[int] = None
    email: Optional[EmailStr] = None
    

# For now will be modified later
class ProjectBase(BaseModel):
    title: str = Field(..., example="AI Resume Builder")
    description: str = Field(..., example="A tool that generates resumes using AI models based on input data.")
    technologies: List[str] = Field(default_factory=list)
    difficulty: Optional[str] = Field(default="Intermediate")
    tags: List[str] = Field(default_factory=list)
    featured: bool = Field(default=False)
    recommended: bool = Field(default=False)
    domain: Optional[str] = Field(default=None)

    # used when inserting into Pinecone
    def pinecone_metadata(self, id: Optional[str] = None) -> dict: #for now we are manually generating the id cause we have to test the db, but later we will first insert the project into postgre along with its generated id and then put into pinecone
        metadata = {
            "title": self.title,
            "technologies": self.technologies,
            "difficulty": self.difficulty,
            "tags": self.tags,
            "featured": self.featured,
            "recommended": self.recommended,
            "domain": self.domain,
        }
        if id:
            metadata["id"] = id
        return metadata

class ProjectCreate(ProjectBase):
    pass

class Project(ProjectBase):
    id: UUID
    created_at: datetime

    class Config:
        orm_mode = True    

class Query(BaseModel):
    query: str
    
class SearchResult(BaseModel):
    id: str
    score: float
    title: str
    technologies: List[str]
    difficulty: str
    tags: List[str]
    featured: bool
    recommended: bool
    domain: str