# ERP Forja — Guía de instalación

## Estructura
```
erp_forja/
├── backend/          ← FastAPI (Python)
│   ├── main.py
│   ├── models.py
│   ├── logic.py
│   ├── requirements.txt
│   └── .env.example
└── frontend/         ← React + Tailwind
    ├── src/App.jsx
    ├── package.json
    └── vite.config.js
```

## Deploy en Railway (recomendado — gratis hasta 5$/mes)

### Base de datos
1. railway.app → New Project → Add PostgreSQL
2. Copiar DATABASE_URL del panel

### Backend
1. New Service → GitHub Repo → carpeta `backend/`
2. Variables de entorno:
   - DATABASE_URL = (de PostgreSQL)
   - SECRET_KEY = (string aleatorio largo, ej: openssl rand -hex 32)
3. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Una vez deployado, hacer POST a /setup/seed → crea datos iniciales

### Frontend
1. New Service → GitHub Repo → carpeta `frontend/`
2. Variables de entorno:
   - VITE_API_URL = URL del backend (ej: https://erp-forja-backend.railway.app)
3. Build command: `npm install && npm run build`
4. Start command: `npx serve dist -p $PORT`

## Desarrollo local

### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # editar con tu DB local
uvicorn main:app --reload
# API en http://localhost:8000
# Docs en http://localhost:8000/docs
```

### Frontend
```bash
cd frontend
npm install
# crear .env.local con: VITE_API_URL=http://localhost:8000
npm run dev
# App en http://localhost:5173
```

### Setup inicial (una sola vez)
```bash
curl -X POST http://localhost:8000/setup/seed
# Crea: admin@forja.com / admin123
# Cambiá la contraseña inmediatamente desde Configuración → Usuarios
```

## Usuarios y roles
- **admin**: crear/editar órdenes, cargar avance, configurar todo
- **operario**: solo lectura — Dashboard y GANTT

## Funcionalidades
- ✅ Dashboard con KPIs y alertas de vencimiento
- ✅ GANTT interactivo con filtro por célula
- ✅ Tabla de órdenes con filtros, estado en tiempo real
- ✅ Carga de avance por turnos + historial
- ✅ Archivado automático al 100% de producción
- ✅ Encadenamiento de órdenes (fecha inicio = fin de la precedente)
- ✅ Detección de conflictos/solapes por célula
- ✅ Registro de actividad completo (quién hizo qué y cuándo)
- ✅ 15 células (5 activas + 10 futuras)
- ✅ Feriados configurables
