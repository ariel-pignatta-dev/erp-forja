from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional
from database import get_db, Usuario, RolUsuario
import os

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

SECRET_KEY = os.getenv("SECRET_KEY", "erp-forja-secret-key-change-in-production")
ALGORITHM  = "HS256"
TOKEN_EXP  = 60 * 24  # 24 horas

# ── Schemas ────────────────────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str
    usuario: dict

class UsuarioCreate(BaseModel):
    nombre: str
    email: str
    password: str
    rol: RolUsuario = RolUsuario.operario

# ── Helpers ────────────────────────────────────────────────────────────────
def create_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=TOKEN_EXP)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Usuario:
    cred_exc = HTTPException(status_code=401, detail="Credenciales inválidas")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if not user_id:
            raise cred_exc
    except JWTError:
        raise cred_exc
    r = await db.execute(select(Usuario).where(Usuario.id == user_id))
    user = r.scalar_one_or_none()
    if not user or not user.activo:
        raise cred_exc
    return user

async def require_admin(user: Usuario = Depends(get_current_user)) -> Usuario:
    if user.rol != RolUsuario.admin:
        raise HTTPException(status_code=403, detail="Se requiere rol admin")
    return user

# ── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Usuario).where(Usuario.email == form.username))
    user = r.scalar_one_or_none()
    if not user or not pwd_context.verify(form.password, user.password):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    token = create_token({"sub": user.id})
    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {"id": user.id, "nombre": user.nombre, "email": user.email, "rol": user.rol}
    }

@router.post("/usuarios", response_model=dict)
async def crear_usuario(data: UsuarioCreate, db: AsyncSession = Depends(get_db),
                        _: Usuario = Depends(require_admin)):
    r = await db.execute(select(Usuario).where(Usuario.email == data.email))
    if r.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email ya registrado")
    user = Usuario(
        nombre=data.nombre, email=data.email,
        password=pwd_context.hash(data.password), rol=data.rol
    )
    db.add(user)
    await db.commit()
    return {"id": user.id, "nombre": user.nombre, "email": user.email, "rol": user.rol}

@router.get("/me")
async def me(user: Usuario = Depends(get_current_user)):
    return {"id": user.id, "nombre": user.nombre, "email": user.email, "rol": user.rol}

@router.get("/usuarios")
async def listar_usuarios(db: AsyncSession = Depends(get_db), _: Usuario = Depends(require_admin)):
    r = await db.execute(select(Usuario).where(Usuario.activo == True))
    users = r.scalars().all()
    return [{"id": u.id, "nombre": u.nombre, "email": u.email, "rol": u.rol} for u in users]
