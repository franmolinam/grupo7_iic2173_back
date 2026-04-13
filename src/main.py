from fastapi import FastAPI

# Inicializar la aplicación
app = FastAPI(
    title="CityExpress API",
    description="Entrega 1 proyecto Arquisis",
    version="1.0.0"
)

@app.get("/")
def read_root():
    return {"message": "¡Bienvenido a la API de CityExpress! El servidor está corriendo."}

@app.get("/health")
def health_check():
    """
    Endpoint útil para que AWS o Docker verifiquen si la API está viva.
    """
    return {"status": "ok"}