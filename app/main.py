from fastapi import FastAPI, Request
import time
from .routers import auth, users, projects, search, course_agent
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys
import json
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from .rate_limit import limiter

# models.Base.metadata.create_all(bind=engine) ##not required anymore as we have alembic now
# makes sure that the database tables are created based on the models defined in the app will comment out later when I implement alembic for migrations



class JsonFormatter(logging.Formatter):
    def format(self, record):
        message = record.getMessage()
        try:
            # If message is JSON-like dict, parse it back
            message = json.loads(message)
        except Exception:
            pass  

        log_record = {
            "level": record.levelname,
            "logger": record.name,
            "message": message,
            "time": self.formatTime(record, self.datefmt),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        return json.dumps(log_record)


# Configure root logger
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler]
)

logger = logging.getLogger("tecolab_app")

class JSONLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        process_time = (time.time() - start_time) * 1000

        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time_ms": round(process_time, 2)
        }

        logger.info(log_data)
        return response

app = FastAPI()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, you can specify a list of allowed origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers
)

app.add_middleware(JSONLoggingMiddleware)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(search.router)
app.include_router(course_agent.router)

@app.get("/")
def root():
    logger.info("API RUNNING")
    return {"message": "Welcome to the FastAPI application for Tecolab! please refer to the documentation for more information."}
    