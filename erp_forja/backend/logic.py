from datetime import date, timedelta
from typing import Optional
import math

FERIADOS_CACHE: set[date] = set()

def set_feriados(feriados: set[date]):
    global FERIADOS_CACHE
    FERIADOS_CACHE = feriados

def es_dia_laboral(d: date, feriados: Optional[set] = None) -> bool:
    fer = feriados if feriados is not None else FERIADOS_CACHE
    return d.weekday() < 6 and d not in fer   # Lunes-Sábado, no feriado

def workday(start: date, n_days: int, feriados: Optional[set] = None) -> date:
    """Calcula la fecha después de n_days días laborables."""
    if n_days <= 0:
        return start
    fer = feriados if feriados is not None else FERIADOS_CACHE
    d = start
    days = 0
    while days < n_days:
        d += timedelta(days=1)
        if es_dia_laboral(d, fer):
            days += 1
    return d

def fecha_inicio_encadenada(
    fecha_fin_anterior: date,
    feriados: Optional[set] = None
) -> date:
    """
    Devuelve el siguiente día laboral después de la fecha_fin_anterior.
    Si la fecha cae en día no laboral, avanza hasta el próximo laboral.
    """
    if fecha_fin_anterior is None:
        return None

    fer = feriados if feriados is not None else FERIADOS_CACHE

    # avanzar 1 día y buscar próximo laboral
    siguiente = fecha_fin_anterior + timedelta(days=1)

    while not es_dia_laboral(siguiente, fer):
        siguiente += timedelta(days=1)

    return siguiente

def calcular_fecha_fin(
    fecha_inicio: date,
    hs_restantes: float,
    hs_dia: float,
    feriados: Optional[set] = None
) -> date:
    """Calcula fecha fin dado horas restantes y horas por día de la célula."""
    if hs_dia <= 0:
        hs_dia = 6.8
    dias_necesarios = max(1, math.ceil(hs_restantes / hs_dia))
    return workday(fecha_inicio, dias_necesarios, feriados)

def detectar_solape(
    orden_id: int,
    celula_id: int,
    fecha_ini: date,
    fecha_fin: date,
    otras_ordenes: list[dict]
) -> bool:
    """
    Retorna True si hay solape con otra orden de la misma célula.
    Solape estricto: fecha_fin de otra > fecha_ini de esta Y fecha_ini de otra < fecha_fin de esta
    """
    for o in otras_ordenes:
        if o["id"] == orden_id:
            continue
        if o["celula_id"] != celula_id:
            continue
        if o["estado"] == "Completada":
            continue
        if o["fecha_ini"] is None or o["fecha_fin"] is None:
            continue
        if o["fecha_ini"] < fecha_fin and o["fecha_fin"] > fecha_ini:
            return True
    return False

def networkdays(start: date, end: date, feriados: Optional[set] = None) -> int:
    """Cuenta días laborables entre start y end (inclusive)."""
    fer = feriados if feriados is not None else FERIADOS_CACHE
    if end < start:
        return 0
    count = 0
    d = start
    while d <= end:
        if es_dia_laboral(d, fer):
            count += 1
        d += timedelta(days=1)
    return count

def calcular_acumulados(ordenes: list[dict]) -> dict:
    """
    Calcula acumulados básicos de un conjunto de órdenes.
    Espera lista de dicts con al menos:
    - cantidad
    - hs_restantes (opcional)

    Devuelve:
    {
        "total_ordenes": int,
        "total_piezas": float,
        "total_horas": float
    }
    """
    total_ordenes = len(ordenes)
    total_piezas = 0
    total_horas = 0

    for o in ordenes:
        total_piezas += float(o.get("cantidad", 0))
        total_horas += float(o.get("hs_restantes", 0))

    return {
        "total_ordenes": total_ordenes,
        "total_piezas": total_piezas,
        "total_horas": total_horas
    }
