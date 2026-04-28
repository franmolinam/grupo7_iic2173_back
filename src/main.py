from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.database import engine
from src.models import Package, CityConnection, PackageEvent

# Crear tablas si no existen
from src.database import Base
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CityExpress API",
    description="Entrega 1 proyecto Arquisis - Los Santos (LSN)",
    version="1.0.0"
)

# CORS para que el frontend pueda consumir la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en producción restringir al dominio del frontend
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