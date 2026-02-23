"""ERP Forja — Backend FastAPI"""
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from datetime import date, datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import os, json, math
from dotenv import load_dotenv

load_dotenv()
from models import (Base, Usuario, Celula, SKU, Feriado, Orden,
                    CargaAvance, AuditLog, EstadoOrden, RolUsuario)
from logic import (calcular_fecha_fin, fecha_inicio_encadenada,
                   detectar_conflicto, calcular_acumulados)

DATABASE_URL = os.getenv("DATABASE_URL","postgresql://postgres:postgres@localhost/erp_forja")
SECRET_KEY   = os.getenv("SECRET_KEY","dev-secret")
ALGORITHM    = "HS256"
TOKEN_EXPIRE = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES","480"))

engine      = create_engine(DATABASE_URL)
SessionLocal= sessionmaker(bind=engine,autoflush=False,autocommit=False)
Base.metadata.create_all(bind=engine)

pwd_ctx = CryptContext(schemes=["bcrypt"])
oauth2  = OAuth2PasswordBearer(tokenUrl="/auth/token")
app     = FastAPI(title="ERP Forja",version="1.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,
                   allow_methods=["*"],allow_headers=["*"])

def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()

def create_token(data):
    p=data.copy(); p["exp"]=datetime.utcnow()+timedelta(minutes=TOKEN_EXPIRE)
    return jwt.encode(p,SECRET_KEY,algorithm=ALGORITHM)

def get_current_user(token:str=Depends(oauth2),db:Session=Depends(get_db)):
    try:
        p=jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
        uid=p.get("sub")
    except JWTError: raise HTTPException(401,"Token inválido")
    u=db.query(Usuario).filter(Usuario.id==int(uid)).first()
    if not u or not u.activo: raise HTTPException(401,"Usuario inactivo")
    return u

def require_admin(u=Depends(get_current_user)):
    if u.rol!=RolUsuario.admin: raise HTTPException(403,"Se requiere admin")
    return u

def audit(db,uid,tabla,rid,accion,detalle,ip=""):
    db.add(AuditLog(usuario_id=uid,tabla=tabla,registro_id=rid,
                    accion=accion,detalle=json.dumps(detalle,default=str),ip=ip))

def get_feriados(db)->set:
    return {f.fecha for f in db.query(Feriado).all()}

def enriquecer_orden(o:Orden,feriados:set)->dict:
    cel=o.celula; hs_dia=cel.hs_dia_lv if cel else 6.8
    cargas=sorted(o.cargas,key=lambda c:c.fecha)
    acums=calcular_acumulados(cargas)
    pzas_prod=acums[-1][1] if acums else 0
    pzas_rest=max(0,o.cantidad-pzas_prod)
    t_unit=o.sku.t_unit_min if o.sku else 0
    hs_est =round(o.cantidad*t_unit/60,2) if t_unit else 0
    hs_rest=round(pzas_rest*t_unit/60,2) if t_unit else hs_est
    f_ini=o.fecha_inicio
    f_ini_encadenada=False
    if not f_ini and o.ot_precede:
        prec=enriquecer_orden(o.ot_precede,feriados)
        if prec["fecha_fin"]:
            f_ini=fecha_inicio_encadenada(prec["fecha_fin"],feriados)
            f_ini_encadenada=True
    f_fin=None
    if f_ini:
        if o.estado==EstadoOrden.completada: f_fin=f_ini
        else: f_fin=calcular_fecha_fin(f_ini,hs_rest,hs_dia,feriados)
    dias_resid=max(0,(f_fin-date.today()).days) if f_fin and o.estado!=EstadoOrden.completada else 0
    pct=round(pzas_prod/o.cantidad*100,1) if o.cantidad>0 else 0
    return dict(id=o.id,nro_ot=o.nro_ot,celula_id=o.celula_id,
                celula_codigo=cel.codigo if cel else "",
                celula_color=cel.color_hex if cel else "#94A3B8",
                sku_id=o.sku_id,sku_codigo=o.sku.codigo if o.sku else "",
                cantidad=o.cantidad,pzas_producidas=pzas_prod,pzas_restantes=pzas_rest,
                hs_estimadas=hs_est,hs_restantes=hs_rest,
                fecha_inicio=f_ini,fecha_fin=f_fin,dias_residuales=dias_resid,
                estado=o.estado,ot_precede_id=o.ot_precede_id,
                ot_precede_nro=o.ot_precede.nro_ot if o.ot_precede else None,
                fecha_inicio_encadenada=f_ini_encadenada,
                notas=o.notas,pct_avance=pct,archivada=o.archivada,
                creada_en=o.creada_en)

# ── Schemas ────────────────────────────────────────────────────────────────
class OrdenIn(BaseModel):
    nro_ot:str; celula_id:int; sku_id:int; cantidad:int
    fecha_inicio:Optional[date]=None; estado:EstadoOrden=EstadoOrden.pendiente
    ot_precede_id:Optional[int]=None; notas:Optional[str]=None

class OrdenUpdate(BaseModel):
    celula_id:Optional[int]=None; sku_id:Optional[int]=None
    cantidad:Optional[int]=None; fecha_inicio:Optional[date]=None
    estado:Optional[EstadoOrden]=None; ot_precede_id:Optional[int]=None
    notas:Optional[str]=None

class CargaIn(BaseModel):
    orden_id:int; fecha:date; turno_1:int=0; turno_2:int=0
    turno_3:int=0; scrap:int=0; notas:Optional[str]=None

class CelulaIn(BaseModel):
    codigo:str; nombre:Optional[str]=None
    turnos_lv:int=1; hs_turno_lv:float=8.0
    turnos_sab:int=3; hs_turno_sab:float=4.0
    efic_lv:float=85.0; efic_sab:float=85.0
    hs_extra_lv:float=0; hs_extra_sab:float=0
    hs_extra_dom:float=0; hs_extra_fer:float=0
    activa:bool=True; color_hex:str="#94A3B8"

class SKUIn(BaseModel):
    codigo:str; descripcion:Optional[str]=None
    material:Optional[str]=None; proceso:Optional[str]=None
    t_unit_min:float; activo:bool=True

class UsuarioCreate(BaseModel):
    nombre:str; email:str; password:str; rol:RolUsuario=RolUsuario.operario

class FeriadoIn(BaseModel):
    fecha:date; descripcion:Optional[str]=None

# ── AUTH ───────────────────────────────────────────────────────────────────
@app.post("/auth/token")
def login(form:OAuth2PasswordRequestForm=Depends(),db:Session=Depends(get_db)):
    u=db.query(Usuario).filter(Usuario.email==form.username).first()
    if not u or not pwd_ctx.verify(form.password,u.password_hash):
        raise HTTPException(401,"Credenciales inválidas")
    return {"access_token":create_token({"sub":str(u.id),"rol":u.rol}),
            "token_type":"bearer","rol":u.rol,"nombre":u.nombre}

@app.get("/auth/me")
def me(u=Depends(get_current_user)):
    return {"id":u.id,"nombre":u.nombre,"email":u.email,"rol":u.rol}

@app.post("/auth/usuarios")
def crear_usuario(data:UsuarioCreate,db=Depends(get_db),admin=Depends(require_admin)):
    if db.query(Usuario).filter(Usuario.email==data.email).first():
        raise HTTPException(400,"Email ya existe")
    u=Usuario(nombre=data.nombre,email=data.email,
              password_hash=pwd_ctx.hash(data.password),rol=data.rol)
    db.add(u); db.commit(); db.refresh(u)
    audit(db,admin.id,"usuarios",u.id,"CREATE",{"email":data.email}); db.commit()
    return {"id":u.id,"nombre":u.nombre,"email":u.email,"rol":u.rol}

@app.get("/auth/usuarios")
def listar_usuarios(db=Depends(get_db),_=Depends(require_admin)):
    return [{"id":u.id,"nombre":u.nombre,"email":u.email,"rol":u.rol,"activo":u.activo}
            for u in db.query(Usuario).all()]

# ── CÉLULAS ────────────────────────────────────────────────────────────────
@app.get("/celulas")
def listar_celulas(db=Depends(get_db),_=Depends(get_current_user)):
    return db.query(Celula).order_by(Celula.codigo).all()

@app.post("/celulas")
def crear_celula(data:CelulaIn,db=Depends(get_db),admin=Depends(require_admin)):
    c=Celula(**data.model_dump()); db.add(c); db.commit(); db.refresh(c)
    audit(db,admin.id,"celulas",c.id,"CREATE",{"codigo":data.codigo}); db.commit()
    return c

@app.put("/celulas/{cid}")
def actualizar_celula(cid:int,data:CelulaIn,db=Depends(get_db),admin=Depends(require_admin)):
    c=db.query(Celula).get(cid)
    if not c: raise HTTPException(404)
    for k,v in data.model_dump().items(): setattr(c,k,v)
    audit(db,admin.id,"celulas",cid,"UPDATE",data.model_dump()); db.commit()
    return c

# ── SKUs ───────────────────────────────────────────────────────────────────
@app.get("/skus")
def listar_skus(db=Depends(get_db),_=Depends(get_current_user)):
    return db.query(SKU).filter(SKU.activo==True).order_by(SKU.codigo).all()

@app.post("/skus")
def crear_sku(data:SKUIn,db=Depends(get_db),admin=Depends(require_admin)):
    if db.query(SKU).filter(SKU.codigo==data.codigo).first():
        raise HTTPException(400,"SKU ya existe")
    s=SKU(**data.model_dump()); db.add(s); db.commit(); db.refresh(s)
    audit(db,admin.id,"skus",s.id,"CREATE",{"codigo":data.codigo}); db.commit()
    return s

@app.put("/skus/{sid}")
def actualizar_sku(sid:int,data:SKUIn,db=Depends(get_db),admin=Depends(require_admin)):
    s=db.query(SKU).get(sid)
    if not s: raise HTTPException(404)
    for k,v in data.model_dump().items(): setattr(s,k,v)
    audit(db,admin.id,"skus",sid,"UPDATE",data.model_dump()); db.commit()
    return s

# ── FERIADOS ───────────────────────────────────────────────────────────────
@app.get("/feriados")
def listar_feriados(db=Depends(get_db),_=Depends(get_current_user)):
    return db.query(Feriado).order_by(Feriado.fecha).all()

@app.post("/feriados")
def agregar_feriado(data:FeriadoIn,db=Depends(get_db),_=Depends(require_admin)):
    f=Feriado(**data.model_dump()); db.add(f); db.commit(); return f

@app.delete("/feriados/{fid}")
def eliminar_feriado(fid:int,db=Depends(get_db),_=Depends(require_admin)):
    f=db.query(Feriado).get(fid)
    if not f: raise HTTPException(404)
    db.delete(f); db.commit(); return {"ok":True}

# ── ÓRDENES ────────────────────────────────────────────────────────────────
@app.get("/ordenes")
def listar_ordenes(celula_id:Optional[int]=None,estado:Optional[str]=None,
                   archivada:bool=False,db=Depends(get_db),_=Depends(get_current_user)):
    feriados=get_feriados(db)
    q=db.query(Orden).filter(Orden.archivada==archivada)
    if celula_id: q=q.filter(Orden.celula_id==celula_id)
    if estado:    q=q.filter(Orden.estado==estado)
    return [enriquecer_orden(o,feriados) for o in
            q.order_by(Orden.celula_id,Orden.fecha_inicio.nullslast()).all()]

@app.get("/ordenes/{oid}")
def get_orden(oid:int,db=Depends(get_db),_=Depends(get_current_user)):
    o=db.query(Orden).get(oid)
    if not o: raise HTTPException(404)
    return enriquecer_orden(o,get_feriados(db))

@app.post("/ordenes")
def crear_orden(data:OrdenIn,req:Request,db=Depends(get_db),admin=Depends(require_admin)):
    if db.query(Orden).filter(Orden.nro_ot==data.nro_ot).first():
        raise HTTPException(400,f"OT {data.nro_ot} ya existe")
    o=Orden(**data.model_dump()); db.add(o); db.commit(); db.refresh(o)
    audit(db,admin.id,"ordenes",o.id,"CREATE",
          {"nro_ot":data.nro_ot},req.client.host if req.client else "")
    db.commit()
    return enriquecer_orden(o,get_feriados(db))

@app.put("/ordenes/{oid}")
def actualizar_orden(oid:int,data:OrdenUpdate,req:Request,
                     db=Depends(get_db),admin=Depends(require_admin)):
    o=db.query(Orden).get(oid)
    if not o: raise HTTPException(404)
    old_estado=o.estado; cambios={}
    for k,v in data.model_dump(exclude_none=True).items():
        if getattr(o,k)!=v:
            cambios[k]={"antes":getattr(o,k),"despues":v}; setattr(o,k,v)
    if data.estado==EstadoOrden.completada and old_estado!=EstadoOrden.completada:
        o.archivada=True; o.archivada_en=datetime.utcnow()
    if cambios:
        audit(db,admin.id,"ordenes",oid,"UPDATE",cambios,
              req.client.host if req.client else "")
    db.commit()
    return enriquecer_orden(o,get_feriados(db))

@app.delete("/ordenes/{oid}")
def eliminar_orden(oid:int,db=Depends(get_db),admin=Depends(require_admin)):
    o=db.query(Orden).get(oid)
    if not o: raise HTTPException(404)
    audit(db,admin.id,"ordenes",oid,"DELETE",{"nro_ot":o.nro_ot})
    db.delete(o); db.commit(); return {"ok":True}

# ── AVANCE ─────────────────────────────────────────────────────────────────
@app.get("/avance/{orden_id}")
def get_avance(orden_id:int,db=Depends(get_db),_=Depends(get_current_user)):
    o=db.query(Orden).get(orden_id)
    if not o: raise HTTPException(404)
    cargas=sorted(o.cargas,key=lambda c:c.fecha)
    acums=calcular_acumulados(cargas)
    return [{"id":c.id,"fecha":c.fecha,"turno_1":c.turno_1,"turno_2":c.turno_2,
             "turno_3":c.turno_3,"scrap":c.scrap,"total_buenas":c.total_buenas,
             "acumulado":acc,"pct":round(acc/o.cantidad*100,1) if o.cantidad else 0,
             "usuario":c.usuario.nombre if c.usuario else "","cargada_en":c.cargada_en,
             "notas":c.notas} for c,acc in acums]

@app.post("/avance")
def cargar_avance(data:CargaIn,req:Request,db=Depends(get_db),admin=Depends(require_admin)):
    o=db.query(Orden).get(data.orden_id)
    if not o: raise HTTPException(404,"Orden no encontrada")
    if o.archivada: raise HTTPException(400,"Orden archivada")
    c=CargaAvance(**data.model_dump(),usuario_id=admin.id)
    db.add(c); db.commit(); db.refresh(c)
    cargas=sorted(o.cargas,key=lambda x:x.fecha)
    acums=calcular_acumulados(cargas)
    total=acums[-1][1] if acums else 0
    if total>=o.cantidad:
        o.estado=EstadoOrden.completada; o.archivada=True; o.archivada_en=datetime.utcnow()
        audit(db,admin.id,"ordenes",o.id,"ARCHIVE",{"motivo":"100% auto"})
    elif o.estado==EstadoOrden.pendiente:
        o.estado=EstadoOrden.activa
    audit(db,admin.id,"cargas_avance",c.id,"CREATE",
          {"orden":o.nro_ot,"fecha":str(data.fecha),"total":c.total_buenas},
          req.client.host if req.client else "")
    db.commit()
    return {"ok":True,"total_buenas":c.total_buenas,"acumulado":total}

@app.put("/avance/{cid}")
def editar_carga(cid:int,data:CargaIn,req:Request,
                 db=Depends(get_db),admin=Depends(require_admin)):
    c=db.query(CargaAvance).get(cid)
    if not c: raise HTTPException(404)
    old={"t1":c.turno_1,"t2":c.turno_2,"t3":c.turno_3,"scrap":c.scrap}
    c.turno_1=data.turno_1;c.turno_2=data.turno_2;c.turno_3=data.turno_3
    c.scrap=data.scrap;c.notas=data.notas
    audit(db,admin.id,"cargas_avance",cid,"UPDATE",
          {"antes":old,"despues":data.model_dump()},
          req.client.host if req.client else "")
    db.commit(); return {"ok":True}

@app.delete("/avance/{cid}")
def eliminar_carga(cid:int,db=Depends(get_db),admin=Depends(require_admin)):
    c=db.query(CargaAvance).get(cid)
    if not c: raise HTTPException(404)
    audit(db,admin.id,"cargas_avance",cid,"DELETE",{"orden_id":c.orden_id})
    db.delete(c); db.commit(); return {"ok":True}

# ── GANTT ──────────────────────────────────────────────────────────────────
@app.get("/gantt")
def gantt(celula_id:Optional[int]=None,db=Depends(get_db),_=Depends(get_current_user)):
    feriados=get_feriados(db)
    q=db.query(Orden).filter(Orden.archivada==False)
    if celula_id: q=q.filter(Orden.celula_id==celula_id)
    tareas=[]
    for o in q.order_by(Orden.celula_id,Orden.fecha_inicio.nullslast()).all():
        e=enriquecer_orden(o,feriados)
        if not e["fecha_inicio"]: continue
        tareas.append({"id":e["id"],"nro_ot":e["nro_ot"],"celula":e["celula_codigo"],
                       "sku":e["sku_codigo"],"color":e["celula_color"],
                       "fecha_ini":e["fecha_inicio"],"fecha_fin":e["fecha_fin"],
                       "pct_avance":e["pct_avance"],"estado":e["estado"],
                       "ot_precede":e["ot_precede_nro"],"cantidad":e["cantidad"],
                       "pzas_producidas":e["pzas_producidas"]})
    return {"tareas":tareas,"feriados":[str(f) for f in feriados],"hoy":str(date.today())}

# ── DASHBOARD ──────────────────────────────────────────────────────────────
@app.get("/dashboard")
def dashboard(db=Depends(get_db),_=Depends(get_current_user)):
    feriados=get_feriados(db)
    ordenes=db.query(Orden).filter(Orden.archivada==False).all()
    enriched=[enriquecer_orden(o,feriados) for o in ordenes]
    por_estado={"Activa":0,"Pausada":0,"Pendiente":0,"Completada":0}
    por_celula={}; alertas=[]
    for e in enriched:
        por_estado[str(e["estado"])]+=1
        cel=e["celula_codigo"]
        if cel not in por_celula:
            por_celula[cel]={"activas":0,"pct_avg":0,"count":0,"color":e["celula_color"]}
        if str(e["estado"]) in ("Activa","Pausada"): por_celula[cel]["activas"]+=1
        por_celula[cel]["pct_avg"]+=e["pct_avance"]; por_celula[cel]["count"]+=1
        if e["dias_residuales"]<=2 and str(e["estado"]) in ("Activa","Pendiente"):
            alertas.append({"nro_ot":e["nro_ot"],"celula":cel,
                             "dias":e["dias_residuales"],
                             "msg":f"{e['nro_ot']} vence en {e['dias_residuales']} día(s)"})
    for cel in por_celula:
        cnt=por_celula[cel]["count"]
        por_celula[cel]["pct_avg"]=round(por_celula[cel]["pct_avg"]/cnt,1) if cnt else 0
    hace7=datetime.utcnow()-timedelta(days=7)
    arch_semana=db.query(Orden).filter(Orden.archivada==True,Orden.archivada_en>=hace7).count()
    return {"por_estado":por_estado,"por_celula":por_celula,
            "alertas":sorted(alertas,key=lambda a:a["dias"]),
            "archivadas_semana":arch_semana,"total_ordenes":len(enriched)}

# ── CONFLICTOS ─────────────────────────────────────────────────────────────
@app.get("/conflictos")
def get_conflictos(db=Depends(get_db),_=Depends(get_current_user)):
    feriados=get_feriados(db)
    enriched=[enriquecer_orden(o,feriados)
              for o in db.query(Orden).filter(Orden.archivada==False).all()]
    otras=[{"id":e["id"],"nro_ot":e["nro_ot"],"celula_id":e["celula_id"],
            "estado":str(e["estado"]),"fecha_ini":e["fecha_inicio"],
            "fecha_fin":e["fecha_fin"]} for e in enriched if e["fecha_inicio"] and e["fecha_fin"]]
    conflictos=[]
    for e in enriched:
        if not e["fecha_inicio"] or not e["fecha_fin"]: continue
        con = detectar_solape(e["id"], e["celula_id"], e["fecha_inicio"], e["fecha_fin"], otras)
        if con: conflictos.append({"nro_ot":e["nro_ot"],"celula":e["celula_codigo"],
                                   "solapa_con":con,"fecha_ini":e["fecha_inicio"],
                                   "fecha_fin":e["fecha_fin"]})
    return conflictos

# ── AUDIT ──────────────────────────────────────────────────────────────────
@app.get("/audit")
def get_audit(limite:int=100,db=Depends(get_db),_=Depends(require_admin)):
    return [{"id":l.id,"usuario":l.usuario.nombre if l.usuario else "sistema",
             "tabla":l.tabla,"accion":l.accion,"detalle":l.detalle,
             "ip":l.ip,"timestamp":l.timestamp}
            for l in db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limite).all()]

# ── SEED ───────────────────────────────────────────────────────────────────
@app.post("/setup/seed")
def seed(db=Depends(get_db)):
    if db.query(Usuario).count()>0: return {"msg":"Ya hay datos"}
    db.add(Usuario(nombre="Admin",email="admin@forja.com",
                   password_hash=pwd_ctx.hash("admin123"),rol=RolUsuario.admin))
    for cod,nom,tlv,hlv,ts,hs,elv,es,clr in [
        ("C69","Célula Nº69",1,8,3,4,85,85,"#3B82F6"),
        ("C101","Célula Nº101",1,8,3,4,85,85,"#10B981"),
        ("C158","Célula Nº158",2,8,3,4,85,85,"#F59E0B"),
        ("C161","Célula Nº161",1,8,3,4,85,85,"#8B5CF6"),
        ("C165","Célula Nº165",3,8,3,4,85,85,"#EF4444")]:
        db.add(Celula(codigo=cod,nombre=nom,turnos_lv=tlv,hs_turno_lv=hlv,
                      turnos_sab=ts,hs_turno_sab=hs,efic_lv=elv,efic_sab=es,color_hex=clr))
    for i in range(1,11):
        db.add(Celula(codigo=f"C-F{i:02d}",nombre=f"Célula Futura {i:02d}",activa=False))
    for cod,t,desc in [("1001XL",1.71,"Pieza estructural XL"),("1049",1.76,"Componente hidráulico"),
                        ("1002",1.33,"Pieza base"),("MOD-44",1.75,"Módulo 44"),("2002",1.95,"Pieza dinámica")]:
        db.add(SKU(codigo=cod,t_unit_min=t,descripcion=desc))
    for m,d,desc in [(1,1,"Año Nuevo"),(2,16,"Carnaval"),(2,17,"Carnaval"),(3,24,"Memoria"),
                     (4,2,"Veteranos"),(4,3,"Viernes Santo"),(5,1,"Trabajador"),(5,25,"Rev.Mayo"),
                     (6,20,"Belgrano"),(7,9,"Independencia"),(8,17,"San Martín"),
                     (10,12,"Diversidad"),(11,20,"Soberanía"),(12,8,"Inmaculada"),(12,25,"Navidad")]:
        db.add(Feriado(fecha=date(2026,m,d),descripcion=desc))
    db.commit()
    return {"msg":"Seed OK — admin@forja.com / admin123"}
