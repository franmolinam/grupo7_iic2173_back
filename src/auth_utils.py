from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
import os
import json
from urllib.request import urlopen


security = HTTPBearer()

async def validate_token(res: HTTPAuthorizationCredentials = Depends(security)):
    AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
    AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
    ALGORITHMS = ["RS256"]

    token = res.credentials
    try:
        # Descarga de JWK estándar desde Auth0
        jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
        jwks = json.loads(urlopen(jwks_url).read())
        unverified_header = jwt.get_unverified_header(token)
        
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"], "kid": key["kid"], "use": key["use"],
                    "n": key["n"], "e": key["e"]
                }
        
        if rsa_key:
            payload = jwt.decode(
                token, rsa_key, algorithms=ALGORITHMS,
                audience=AUTH0_AUDIENCE,
                issuer=f"https://{AUTH0_DOMAIN}/"
            )
            return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    raise HTTPException(status_code=401, detail="No se pudo validar el token.")

def is_admin(payload):
    admins = [
        admin.strip()
        for admin in os.getenv("ADMIN_USERS", "").split(",")
        if admin.strip()
    ]

    return payload.get("sub") in admins

def require_admin(
    payload: dict = Depends(validate_token)
):
    if not is_admin(payload):
        raise HTTPException(
            status_code=403,
            detail="Admin only"
        )

    return payload