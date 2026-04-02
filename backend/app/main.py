from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes.upload import router as upload_router
from app.routes.pdf import router as pdf_router
from app.services.query import router as query_router
from app.db.database import Base, engine
from app.models import document
from app.config import CORS_ORIGINS, UPLOAD_DIR

import os

# =========================
# DB INIT
# =========================
Base.metadata.create_all(bind=engine)

# =========================
# APP
# =========================
app = FastAPI()

# =========================
# PATHS
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.makedirs(UPLOAD_DIR, exist_ok=True)

# =========================
# FINAL CORS FIX
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# STATIC FILES (IMPORTANT)
# =========================
app.mount(
    "/uploads",
    StaticFiles(directory=UPLOAD_DIR),
    name="uploads"
)

# =========================
# HEALTH CHECK
# =========================
@app.get("/")
def root():
    return {
        "status": "ok",
        "uploads_dir": UPLOAD_DIR
    }

# =========================
# ROUTES
# =========================
app.include_router(upload_router, prefix="/api")
app.include_router(query_router, prefix="/api")
app.include_router(pdf_router, prefix="/api")
