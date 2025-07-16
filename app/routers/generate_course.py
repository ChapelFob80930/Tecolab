from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import database, schemas, models, utils, oauth2
from ..course_creator_agent import agent
from uuid import uuid4
import json
from ..config import settings

router = APIRouter(prefix = "/generate", tags = ['manage-show-projects-vectorDB'])

@router.post("/")
def generate_course(): #not implemented yet
    pass