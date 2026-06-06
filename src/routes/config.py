import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator

from src.database import get_db
from src.auth_utils import validate_token
from src.models.branch_config import BranchConfig

router = APIRouter(prefix="/config", tags=["config"])

FPRICE_DEFAULT = float(os.getenv("FPRICE", "1.0"))

# Para leer el fprice de la BD
def get_fprice(db: Session) -> float:
    row = db.query(BranchConfig).filter_by(key="fprice").first()
    # usa el default del .env si no existe
    return row.value if row else FPRICE_DEFAULT


class FpriceUpdate(BaseModel):
    value: float

    @field_validator("value")
    @classmethod
    def rango_valido(cls, v):
        if not (0.5 <= v <= 2.0):
            raise ValueError("fprice debe estar entre 0.5 y 2.0")
        return v


# GET /config/fprice — público, el front lo usa para mostrar el factor actual
@router.get("/fprice")
def read_fprice(db: Session = Depends(get_db)):
    return {"fprice": get_fprice(db)}


# PUT /config/fprice — solo admins
@router.put("/fprice")
def update_fprice(
    body: FpriceUpdate,
    db: Session = Depends(get_db),
    payload: dict = Depends(validate_token),
    #payload = {"sub": "test-user"}  # temporal
):
    row = db.query(BranchConfig).filter_by(key="fprice").first()
    if row:
        row.value = body.value
    else:
        row = BranchConfig(key="fprice", value=body.value)
        db.add(row)
    db.commit()
    return {"fprice": row.value, "message": "fprice actualizado correctamente"}