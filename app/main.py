from fastapi import FastAPI


from app.routes.upload import router as upload_router
from app.services.query import router as query_router
from app.routes.ask import router as ask_router

app = FastAPI()



# Rota raiz
@app.get("/")
def root():
    return {"status": "ok"}

# Rotas
app.include_router(upload_router, prefix="/api")
app.include_router(query_router, prefix="/api")
app.include_router(ask_router, prefix="/api")