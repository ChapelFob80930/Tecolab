from fastapi import FastAPI
from .routers import auth, users, projects, search
from .config import settings
from fastapi.middleware.cors import CORSMiddleware
from .database import engine
from . import models

models.Base.metadata.create_all(bind=engine) 
# makes sure that the database tables are created based on the models defined in the app will comment out later when I implement alembic for migrations

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, you can specify a list of allowed origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(search.router)

@app.get("/")
def root():
    return {"message": "Welcome to the FastAPI application for Tecolab! please refer to the documentation for more information."}
    