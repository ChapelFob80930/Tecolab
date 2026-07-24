from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from .. import schemas, utils, oauth2
from ..models import models
from ..repository import database

router = APIRouter(tags = ['authentication'])

@router.post("/login", response_model=schemas.Token)
def login(user_credentials: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    
    #oauth2PasswordRequestForm is a class that takes care of parsing the form data
    #and returns an object with the username and password attributes
    
    user = db.query(models.User).filter(models.User.email == user_credentials.username).first()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Credentials")
    
    if not utils.verify(user_credentials.password, user.password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Credentials")
    
    
    access_token = oauth2.create_access_token(data={"user_id":user.id, "role": user.role} )
    
    return {"access_token": access_token, "token_type": "bearer"}