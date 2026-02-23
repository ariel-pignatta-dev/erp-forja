# ── celulas.py ──────────────────────────────────────────────────────────────
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from database import get_db, Celula, Usuario
from routers.auth import get_current_user, require_admin

router = APIRouter()

class CelulaUpdate(BaseModel):
    nombre: Optional[str] = None
    turnos_lv: Optional[int] = None
    hs_turno_lv: Optional[float] = None
    turnos_sab: Optional[int] = None
    hs_turno_sab: Optional[float] = None
    efic_lv: Optional[float] = None
    efic_sab: Optional[float] = None
    hs_extra_lv: Optional[float] = None
    hs_extra_sab: Optional[float] = None
    color: Optional[str] = None
    activa: Optional[bool] = None

def cel_dict(c: Celula) -> dict:
    return {
        "id": c.id, "codigo": c.codigo, "nombre": c.nombre,
        "turnos_lv": c.turnos_lv, "hs_turno_lv": c.hs_turno_lv,
        "turnos_sab": c.turnos_sab, "hs_turno_sab": c.hs_turno_sab,
        "efic_lv": c.efic_lv, "efic_sab": c.efic_sab,
        "hs_extra_lv": c.hs_extra_lv, "hs_extra_sab": c.hs_extra_sab,
        "hs_dia_base": c.hs_dia_base, "hs_dia_total": c.hs_dia_total,
        "color": c.color, "activa": c.activa,
    }

@router.get("")
async def listar_celulas(db: AsyncSession = Depends(get_db),
                         user: Usuario = Depends(get_current_user)):
    r = await db.execute(select(Celula).order_by(Celula.codigo))
    return [cel_dict(c) for c in r.scalars().all()]

@router.patch("/{celula_id}")
async def editar_celula(celula_id: int, data: CelulaUpdate,
                        db: AsyncSession = Depends(get_db),
                        user: Usuario = Depends(require_admin)):
    r = await db.execute(select(Celula).where(Celula.id == celula_id))
    c = r.scalar_one_or_none()
    if not c:
        raise HTTPException(404, "Célula no encontrada")
    for f, v in data.model_dump(exclude_none=True).items():
        setattr(c, f, v)
    await db.commit()
    return cel_dict(c)
