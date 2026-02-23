from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import date

from database import get_db, Orden, Feriado, Celula, Usuario, EstadoOrden
from routers.auth import get_current_user
from logic import calcular_fecha_fin, set_feriados

router = APIRouter()

@router.get("")
async def dashboard_data(db: AsyncSession = Depends(get_db),
                         user: Usuario = Depends(get_current_user)):
    today = date.today()

    r_cel = await db.execute(select(Celula).where(Celula.activa == True).order_by(Celula.codigo))
    celulas = r_cel.scalars().all()

    r_ord = await db.execute(
        select(Orden).options(
            selectinload(Orden.celula), selectinload(Orden.sku), selectinload(Orden.avances)
        ).where(Orden.archivada == False)
    )
    ordenes = r_ord.scalars().all()

    r_fer = await db.execute(select(Feriado))
    feriados = {f.fecha for f in r_fer.scalars().all()}
    set_feriados(feriados)

    stats = {
        "total_ordenes": len(ordenes),
        "activas":       sum(1 for o in ordenes if o.estado == EstadoOrden.activa),
        "pendientes":    sum(1 for o in ordenes if o.estado == EstadoOrden.pendiente),
        "pausadas":      sum(1 for o in ordenes if o.estado == EstadoOrden.pausada),
        "alertas":       [],
    }

    por_celula = []
    for cel in celulas:
        ords_activas = [o for o in ordenes if o.celula_id == cel.id and o.estado == EstadoOrden.activa]

        pzas_hoy = sum(
            a.total_buenas
            for o in ords_activas
            for a in o.avances
            if a.fecha == today
        )

        todas_fechas = [a.fecha for o in ords_activas for a in o.avances]
        ultima_carga = max(todas_fechas) if todas_fechas else None
        sin_carga = (ultima_carga is None or ultima_carga < today) and bool(ords_activas)

        if sin_carga:
            stats["alertas"].append({"tipo": "sin_carga", "celula": cel.codigo})

        # Órdenes por vencer
        vencen_hoy = vencen_pronto = 0
        for o in ords_activas:
            if not o.fecha_inicio: continue
            t_unit = o.sku.t_unit if o.sku else 0
            pzas_rest = max(0, o.cantidad - sum(a.total_buenas for a in o.avances))
            hs_rest = round(pzas_rest * t_unit / 60, 2) if t_unit else 0
            fecha_fin = calcular_fecha_fin(o.fecha_inicio, hs_rest, cel.hs_dia_total, feriados)
            dias = (fecha_fin - today).days
            if dias <= 0:
                vencen_hoy += 1
                stats["alertas"].append({"tipo": "vence_hoy", "orden": o.numero, "celula": cel.codigo})
            elif dias <= 2:
                vencen_pronto += 1
                stats["alertas"].append({"tipo": "vence_pronto", "orden": o.numero, "celula": cel.codigo, "dias": dias})

        por_celula.append({
            "celula_id":      cel.id,
            "codigo":         cel.codigo,
            "nombre":         cel.nombre,
            "color":          cel.color,
            "ordenes_activas":len(ords_activas),
            "pzas_hoy":       pzas_hoy,
            "sin_carga":      sin_carga,
            "ultima_carga":   ultima_carga.isoformat() if ultima_carga else None,
            "vencen_hoy":     vencen_hoy,
            "vencen_pronto":  vencen_pronto,
        })

    return {**stats, "por_celula": por_celula, "fecha": today.isoformat()}
