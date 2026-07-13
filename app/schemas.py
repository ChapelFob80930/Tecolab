from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Annotated, List, Literal, Dict
from uuid import UUID, uuid4

from enum import Enum

class RoleEnum(str, Enum):
    admin = "admin"
    user = "user"

class UserBase(BaseModel):
    email: EmailStr = Field(..., description="The user's email address")
    first_name: str = Field(...,min_length=1, description="The user's first name")
    last_name: str = Field(...,min_length=1, description="The user's last name")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="The date and time when the user was created")
    
class UserCreate(UserBase):
    id: str = Field(default_factory=lambda: "user_"+str(uuid4()), description="The user's unique identifier")
    password: str = Field(..., min_length=6, description="The user's password")
    skills: Optional[str] = Field(None, description="The user's skills")
    goal: Optional[str] = Field(None, description="The user's goal")
    experience: Optional[str] = Field(None, description="The user's experience")
    wants_to_learn: Optional[str] = Field(None, description="What the user wants to learn")
    
class UserOut(BaseModel):
    id: str
    email: EmailStr
    created_at: datetime
    first_name: str
    last_name: str
    role: RoleEnum
    skills: Optional[str] = None
    goal: Optional[str] = None
    experience: Optional[str] = None
    wants_to_learn: Optional[str] = None
    
    class Config:
        from_attributes = True
    
class Token(BaseModel):
    access_token: str
    token_type: str
    
class TokenData(BaseModel):
    id: Optional[str] = None
    role: Optional[str] = None
    

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
        from_attributes = True    

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
    

class CoursePrompt(BaseModel):
    topic: str  # e.g. "LangChain"
    level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    use_scraping: bool = False  # If True, try to pull web data
    include_code: bool = True  # If True, include code examples
    audience: Optional[str] = None #can be null or any audience the admin finds suitable
    duration: Optional[str] = None #can be null and the ai generates it on its own or any duration the admin finds suitable
    custom_urls: Optional[List[str]] = Field(default_factory=list)
    # author_id: str

class Module(BaseModel):
    title: str
    summary: str
    code_examples: str = ""
    resources: Optional[Dict[str, str]] = Field(default_factory=dict)       # External links or references
    video_links: Optional[List[str]] = Field(default_factory=list)
    scraping_resources: Optional[Dict[str, str]] = Field(default_factory=dict)

class CourseOutline(BaseModel):
    title: str
    description: str
    modules: List[Module]  # List of {title, summary}
    prerequisites: List[str]
    will_learn: List[str]  # Key skills/outcomes, e.g. ["Build agents with LangChain", "Use vector databases"]
    estimated_time: str
    # rating: Optional[float]
    # thumbnail_url: str
    module_difficulty: Dict[str,str]
    

# --- Start Graph Run ---
class StartRequest(BaseModel):
    human_request: str

# --- Resume Paused Graph Run ---
class ResumeRequest(BaseModel):
    thread_id: str
    review_action: Optional[Literal["approve", "reject"]] = None
    user_edit_request: Optional[str] = None  # Only required if review_action is "reject"

# --- Minimal API Response ---
class GraphResponse(BaseModel):
    thread_id: str
    run_status: Literal["finished", "user_feedback"]
    assistant_response: Optional[str] = None    
