from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from src.auth_utils import validate_token
from src.routes.packages import router as packages_router
from src.routes.connections import router as connections_router


app = FastAPI(
    title="CityExpress API",
    description="Entrega 1 proyecto Arquisis - Los Santos (LSN)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://eliasapi.me"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enable proxy trust - Si es que necesitamos integrar Nginx or any reverse proxy
# app.state.trust_proxy = True

@app.get("/")
def read_root():
    return {"message": "¡Bienvenido a CityExpress - Los Santos (LSN)!"}

@app.get("/health")
def health_check():
    return {"status": "ok", "city": "LSN"}

# Ruta privada que necesita token para acceder (Auth0)
@app.get("/api/private", dependencies=[Depends(validate_token)])
def private_route(payload: dict = Depends(validate_token)):
    return {
        "message": "Tienes acceso a esta ruta privada",
        "user_id": payload.get("sub"), 
        "info": "Autenticación JWK validada con éxito"
    }
    
# Maneja los errores dependiendo del tipo de error
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code in [401, 403]:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "error": "authentication_failed" if exc.status_code == 401 else "access_denied",
                "message": "No tienes permiso para acceder a este recurso",
                "details": exc.detail
            }
        )
    # Maneja el resto de errores HTTP (400, 404, etc)
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": exc.status_code, "detail": exc.detail}
    )
  
app.include_router(packages_router)
app.include_router(connections_router)