import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS, UPLOAD_DIR
from app.db.database import Base, engine
from app.models import auth_session, chat_session, document, password_reset_token, user
from app.routes.auth import router as auth_router
from app.routes.chats import router as chats_router
from app.routes.pdf import router as pdf_router
from app.routes.system import router as system_router
from app.routes.upload import router as upload_router
from app.services.query import router as query_router


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("studyiacopilot.app")


if engine is not None:
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        logger.warning("Database initialization skipped: %s", exc)


app = FastAPI(title="StudyIA Copilot API")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "status": "ok",
        "uploads_dir": UPLOAD_DIR,
        "cors_origins": CORS_ORIGINS,
    }


app.include_router(auth_router, prefix="/api")
app.include_router(chats_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(query_router, prefix="/api")
app.include_router(pdf_router, prefix="/api")
app.include_router(system_router, prefix="/api")
