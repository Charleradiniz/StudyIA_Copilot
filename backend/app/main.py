from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.upload import router as upload_router
from app.services.query import router as query_router

app = FastAPI()

# 🔥 CORS (resolve seu erro do frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rota raiz
@app.get("/")
def root():
    return {"status": "ok"}

# Rotas
app.include_router(upload_router, prefix="/api")
app.include_router(query_router, prefix="/api")
