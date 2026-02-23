# routers/avance.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
import json

from database import get_db, AvanceDiario, Orden, LogCambio, Usuario
from routers.auth import get_current_user, require_admin

router = APIRouter()

class AvanceCreate(BaseModel):
    orden_id: int
    fecha: date
    t1_piezas: int = 0
    t2_piezas: int = 0
    t3_piezas: int = 0
    scrap: int = 0
    notas: Optional[str] = None

@router.get("")
async def listar_avances(orden_id: Optional[int] = None, db: AsyncSession = Depends(get_db),
                         user: Usuario = Depends(get_current_user)):
    q = select(AvanceDiario).options(selectinload(AvanceDiario.usuario),
                                      selectinload(AvanceDiario.orden))
    if orden_id:
        q = q.where(AvanceDiario.orden_id == orden_id)
    q = q.order_by(AvanceDiario.fecha)
    r = await db.execute(q)
    avances = r.scalars().all()
    return [{
        "id": a.id, "orden_id": a.orden_id,
        "orden_numero": a.orden.numero if a.orden else None,
        "fecha": a.fecha.isoformat(),
        "t1_piezas": a.t1_piezas, "t2_piezas": a.t2_piezas,
        "t3_piezas": a.t3_piezas, "scrap": a.scrap,
        "total_buenas": a.total_buenas,
        "notas": a.notas,
        "cargado_por": a.usuario.nombre if a.usuario else None,
        "cargado_en": a.cargado_en.isoformat(),
    } for a in avances]

@router.post("")
async def cargar_avance(data: AvanceCreate, db: AsyncSession = Depends(get_db),
                        user: Usuario = Depends(require_admin)):
    r = await db.execute(select(Orden).where(Orden.id == data.orden_id))
    if not r.scalar_one_or_none():
        raise HTTPException(404, "Orden no encontrada")

    av = AvanceDiario(**data.model_dump(), usuario_id=user.id)
    db.add(av)
    log = LogCambio(usuario_id=user.id, orden_id=data.orden_id, accion="cargar_avance",
                    detalle=json.dumps({
                        "fecha": data.fecha.isoformat(),
                        "total": data.t1_piezas + data.t2_piezas + data.t3_piezas,
                        "scrap": data.scrap
                    }))
    db.add(log)
    await db.commit()
    return {"ok": True, "id": av.id, "total_buenas": av.total_buenas}

@router.delete("/{avance_id}")
async def eliminar_avance(avance_id: int, db: AsyncSession = Depends(get_db),
                          user: Usuario = Depends(require_admin)):
    r = await db.execute(select(AvanceDiario).where(AvanceDiario.id == avance_id))
    av = r.scalar_one_or_none()
    if not av:
        raise HTTPException(404, "Avance no encontrado")
    log = LogCambio(usuario_id=user.id, orden_id=av.orden_id, accion="eliminar_avance",
                    detalle=json.dumps({"fecha": av.fecha.isoformat()}))
    db.add(log)
    await db.delete(av)
    await db.commit()
    return {"ok": True}
