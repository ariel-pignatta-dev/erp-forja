# ── skus.py ────────────────────────────────────────────────────────────────
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from database import get_db, SKU, Usuario
from routers.auth import get_current_user, require_admin

router = APIRouter()

class SKUCreate(BaseModel):
    codigo: str
    descripcion: str
    material: Optional[str] = None
    proceso: Optional[str] = None
    t_unit: float = 0.0
    observaciones: Optional[str] = None

class SKUUpdate(BaseModel):
    descripcion: Optional[str] = None
    material: Optional[str] = None
    proceso: Optional[str] = None
    t_unit: Optional[float] = None
    observaciones: Optional[str] = None
    activo: Optional[bool] = None

def sku_dict(s: SKU) -> dict:
    return {"id": s.id, "codigo": s.codigo, "descripcion": s.descripcion,
            "material": s.material, "proceso": s.proceso, "t_unit": s.t_unit,
            "observaciones": s.observaciones, "activo": s.activo}

@router.get("")
async def listar_skus(db: AsyncSession = Depends(get_db),
                      user: Usuario = Depends(get_current_user)):
    r = await db.execute(select(SKU).where(SKU.activo == True).order_by(SKU.codigo))
    return [sku_dict(s) for s in r.scalars().all()]

@router.post("")
async def crear_sku(data: SKUCreate, db: AsyncSession = Depends(get_db),
                    user: Usuario = Depends(require_admin)):
    r = await db.execute(select(SKU).where(SKU.codigo == data.codigo))
    if r.scalar_one_or_none():
        raise HTTPException(400, f"SKU {data.codigo} ya existe")
    s = SKU(**data.model_dump())
    db.add(s); await db.commit()
    return sku_dict(s)

@router.patch("/{sku_id}")
async def editar_sku(sku_id: int, data: SKUUpdate,
                     db: AsyncSession = Depends(get_db),
                     user: Usuario = Depends(require_admin)):
    r = await db.execute(select(SKU).where(SKU.id == sku_id))
    s = r.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "SKU no encontrado")
    for f, v in data.model_dump(exclude_none=True).items():
        setattr(s, f, v)
    await db.commit()
    return sku_dict(s)
