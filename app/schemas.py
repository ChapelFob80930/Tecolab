from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Annotated

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
    
    