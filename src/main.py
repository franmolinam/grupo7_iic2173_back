from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routes.packages import router as packages_router
from src.routes.connections import router as connections_router

app = FastAPI(
    title="CityExpress API",
    description="Entrega 1 proyecto Arquisis - Los Santos (LSN)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "¡Bienvenido a CityExpress - Los Santos (LSN)!"}

@app.get("/health")
def health_check():
    return {"status": "ok", "city": "LSN"}

app.include_router(packages_router)
app.include_router(connections_router)
