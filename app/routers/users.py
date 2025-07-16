import os
from .. import schemas,models, utils
from fastapi import FastAPI, Response, status, HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import RoleEnum

router = APIRouter( prefix = "/users", tags = ['Users']) #prefix for all routes in this router will be /users

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.UserOut)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    
    #hashing the password - user.password
    hashed_password = utils.hash(user.password)
    user.password = hashed_password
    
    new_user = models.User(**user.model_dump(exclude={"role"}))#unpacking the post dictionary to match the Post model
    
    new_user.role = RoleEnum.user
    if user.email.endswith("@tecolab.in"):
        new_user.role = RoleEnum.admin
    
    #if it is not possible to make email ending with @tecolab.dev then we uncomment below code and add required env variables
        
    TRUSTED_ADMINS = os.getenv("TRUSTED_ADMIN_EMAILS", "").split(",")

    if user.email in TRUSTED_ADMINS:
        new_user.role = RoleEnum.admin
    
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)  # Refresh the instance to get the updated data from the database
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error creating user: {str(e)}")
        # Rollsback the transaction in case of an error, preventing partial commits.
        #HTTP 400 means Bad Request, indicating that the request was invalid or cannot be served or some not nullable field is null
        
    return new_user

@router.get("/{id}", response_model = schemas.UserOut)
def get_user(id:int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == id).first()
    
    if not user:
        raise HTTPException(status_code = status.HTTP_404_NOT_FOUND, detail = f"User with id {id} does not exist")
    
    return user