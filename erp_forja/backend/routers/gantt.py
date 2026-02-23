from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional

from database import get_db, Orden, Feriado, Usuario, EstadoOrden
from routers.auth import get_current_user
from logic import calcular_fecha_fin, set_feriados

router = APIRouter()

@router.get("")
async def gantt_data(
    celula_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    r = await db.execute(select(Feriado))
    feriados = {f.fecha for f in r.scalars().all()}
    set_feriados(feriados)

    q = select(Orden).options(
        selectinload(Orden.celula),
        selectinload(Orden.sku),
        selectinload(Orden.avances),
        selectinload(Orden.precede),
    ).where(
        Orden.archivada == False,
        Orden.fecha_inicio != None,
    )
    if celula_id:
        q = q.where(Orden.celula_id == celula_id)
    q = q.order_by(Orden.celula_id, Orden.fecha_inicio)

    r = await db.execute(q)
    ordenes = r.scalars().all()

    tareas = []
    for o in ordenes:
        acum = 0
        for av in sorted(o.avances, key=lambda a: a.fecha):
            acum += av.total_buenas
        pzas_prod = acum
        pzas_rest = max(0, o.cantidad - pzas_prod)
        t_unit = o.sku.t_unit if o.sku else 0
        hs_rest = round(pzas_rest * t_unit / 60, 2) if t_unit else 0
        hs_dia = o.celula.hs_dia_total if o.celula else 6.8
        fecha_fin = calcular_fecha_fin(o.fecha_inicio, hs_rest, hs_dia, feriados)
        pct = round(pzas_prod / o.cantidad * 100, 1) if o.cantidad else 0
        ultima = max((a.fecha for a in o.avances), default=None) if o.avances else None

        tareas.append({
            "id":             o.id,
            "numero":         o.numero,
            "celula_id":      o.celula_id,
            "celula_codigo":  o.celula.codigo if o.celula else "",
            "celula_color":   o.celula.color if o.celula else "#94A3B8",
            "sku_codigo":     o.sku.codigo if o.sku else "",
            "cantidad":       o.cantidad,
            "estado":         o.estado,
            "fecha_inicio":   o.fecha_inicio.isoformat(),
            "fecha_fin":      fecha_fin.isoformat(),
            "pct_avance":     pct,
            "pzas_producidas":pzas_prod,
            "hs_restantes":   hs_rest,
            "ultima_carga":   ultima.isoformat() if ultima else None,
            "ot_precede":     o.precede.numero if o.precede else None,
            "notas":          o.notas,
        })

    return {"tareas": tareas, "feriados": [f.isoformat() for f in feriados]}
