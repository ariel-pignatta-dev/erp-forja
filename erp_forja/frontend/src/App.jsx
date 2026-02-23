import { useState, useEffect, useCallback, useRef } from "react"

// ── API ─────────────────────────────────────────────────────────────────────
const API = import.meta.env.VITE_API_URL || "http://localhost:8000"

async function api(path, opts = {}) {
  const token = localStorage.getItem("token")
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json",
               ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    ...opts,
  })
  if (res.status === 401) { localStorage.clear(); window.location.reload() }
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || "Error") }
  return res.json()
}
const get  = p          => api(p)
const post = (p, d)     => api(p, { method:"POST", body: JSON.stringify(d) })
const put  = (p, d)     => api(p, { method:"PUT",  body: JSON.stringify(d) })
const del  = p          => api(p, { method:"DELETE" })

// ── Helpers ─────────────────────────────────────────────────────────────────
const fmtDate = d => d ? new Date(d+"T12:00:00").toLocaleDateString("es-AR",{day:"2-digit",month:"2-digit"}) : "—"
const fmtDateFull = d => d ? new Date(d+"T12:00:00").toLocaleDateString("es-AR",{day:"2-digit",month:"2-digit",year:"numeric"}) : "—"

const ESTADO_CLR = {
  Activa:    { bg:"bg-blue-100",   text:"text-blue-700",  dot:"bg-blue-500"  },
  Pausada:   { bg:"bg-amber-100",  text:"text-amber-700", dot:"bg-amber-500" },
  Pendiente: { bg:"bg-slate-100",  text:"text-slate-600", dot:"bg-slate-400" },
  Completada:{ bg:"bg-green-100",  text:"text-green-700", dot:"bg-green-500" },
}

function Badge({ estado }) {
  const c = ESTADO_CLR[estado] || ESTADO_CLR.Pendiente
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${c.bg} ${c.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`}/>
      {estado}
    </span>
  )
}

function Spinner() {
  return <div className="flex items-center justify-center h-32">
    <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"/>
  </div>
}

function Alert({ tipo, msg, onClose }) {
  const base = tipo==="error"
    ? "bg-red-50 border-red-200 text-red-800"
    : "bg-green-50 border-green-200 text-green-800"
  return (
    <div className={`flex items-center justify-between p-3 border rounded-lg text-sm ${base}`}>
      <span>{tipo==="error" ? "⚠️" : "✅"} {msg}</span>
      {onClose && <button onClick={onClose} className="ml-2 opacity-60 hover:opacity-100">✕</button>}
    </div>
  )
}

// ── LOGIN ────────────────────────────────────────────────────────────────────
function Login({ onLogin }) {
  const [form, setForm] = useState({ email:"", password:"" })
  const [err,  setErr]  = useState("")
  const [loading, setLoading] = useState(false)

  async function submit(e) {
    e.preventDefault(); setErr(""); setLoading(true)
    try {
      const fd = new URLSearchParams()
      fd.append("username", form.email); fd.append("password", form.password)
      const r = await fetch(`${API}/auth/token`,{ method:"POST", body:fd })
      if (!r.ok) { setErr("Email o contraseña incorrectos"); setLoading(false); return }
      const d = await r.json()
      localStorage.setItem("token", d.access_token)
      localStorage.setItem("rol",   d.rol)
      localStorage.setItem("nombre",d.nombre)
      onLogin(d)
    } catch { setErr("No se pudo conectar al servidor") }
    setLoading(false)
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">🏭</div>
          <h1 className="text-2xl font-bold text-white">ERP Forja</h1>
          <p className="text-slate-400 text-sm mt-1">Sistema de producción</p>
        </div>
        <form onSubmit={submit} className="bg-white rounded-2xl shadow-2xl p-8 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
            <input type="email" value={form.email}
              onChange={e=>setForm(f=>({...f,email:e.target.value}))}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="admin@forja.com" required/>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Contraseña</label>
            <input type="password" value={form.password}
              onChange={e=>setForm(f=>({...f,password:e.target.value}))}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              required/>
          </div>
          {err && <Alert tipo="error" msg={err}/>}
          <button type="submit" disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 rounded-lg transition disabled:opacity-60">
            {loading ? "Ingresando…" : "Ingresar"}
          </button>
        </form>
      </div>
    </div>
  )
}

// ── DASHBOARD ────────────────────────────────────────────────────────────────
function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    get("/dashboard").then(d => { setData(d); setLoading(false) })
  }, [])

  if (loading) return <Spinner/>
  const { por_estado, por_celula, alertas, archivadas_semana, total_ordenes } = data

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-slate-800">Dashboard</h2>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label:"Activas",    val:por_estado.Activa,    color:"text-blue-600",  bg:"bg-blue-50"   },
          { label:"Pendientes", val:por_estado.Pendiente, color:"text-slate-600", bg:"bg-slate-50"  },
          { label:"Pausadas",   val:por_estado.Pausada,   color:"text-amber-600", bg:"bg-amber-50"  },
          { label:"Arch. 7d",   val:archivadas_semana,    color:"text-green-600", bg:"bg-green-50"  },
        ].map(k => (
          <div key={k.label} className={`${k.bg} rounded-xl p-4`}>
            <div className={`text-3xl font-bold ${k.color}`}>{k.val}</div>
            <div className="text-sm text-slate-500 mt-1">{k.label}</div>
          </div>
        ))}
      </div>

      {/* Alertas */}
      {alertas.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <h3 className="font-semibold text-red-700 mb-2">⚠️ Alertas de vencimiento</h3>
          <div className="space-y-1">
            {alertas.map((a,i) => (
              <div key={i} className="flex items-center gap-2 text-sm text-red-700">
                <span className="font-mono font-bold">{a.nro_ot}</span>
                <span className="text-red-400">·</span>
                <span>{a.celula}</span>
                <span className="text-red-400">·</span>
                <span className={a.dias === 0 ? "font-bold" : ""}>
                  {a.dias === 0 ? "Vence hoy" : `${a.dias} día(s)`}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Por célula */}
      <div>
        <h3 className="font-semibold text-slate-700 mb-3">Estado por célula</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {Object.entries(por_celula).map(([cel, info]) => (
            <div key={cel} className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="w-3 h-3 rounded-full" style={{background:info.color}}/>
                <span className="font-semibold text-slate-800">{cel}</span>
                <span className="ml-auto text-sm text-slate-500">{info.activas} activas</span>
              </div>
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all"
                  style={{width:`${info.pct_avg}%`, background:info.color}}/>
              </div>
              <div className="text-xs text-slate-500 mt-1 text-right">{info.pct_avg}% avance prom.</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── GANTT ────────────────────────────────────────────────────────────────────
function GanttBar({ tarea, dias, fechaMin }) {
  const ini = new Date(tarea.fecha_ini + "T12:00:00")
  const fin = new Date(tarea.fecha_fin + "T12:00:00")
  const start = Math.max(0, Math.round((ini - fechaMin) / 86400000))
  const dur   = Math.max(1, Math.round((fin  - ini)     / 86400000) + 1)
  const avPx  = Math.round(dur * tarea.pct_avance / 100)
  const completada = tarea.estado === "Completada"

  return (
    <div className="relative h-5 rounded overflow-hidden"
      style={{ marginLeft:`${start * 28}px`, width:`${dur * 28}px` }}>
      <div className="absolute inset-0 rounded opacity-30"
        style={{ background: completada ? "#94A3B8" : tarea.color }}/>
      <div className="absolute inset-y-0 left-0 rounded"
        style={{ width:`${avPx * 28}px`, background: completada ? "#94A3B8" : "#0369A1" }}/>
      <div className="absolute inset-0 flex items-center px-1">
        <span className="text-white text-xs font-bold truncate" style={{fontSize:"10px"}}>
          {tarea.nro_ot}
        </span>
      </div>
    </div>
  )
}

function Gantt() {
  const [data,     setData]     = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [filtroCel,setFiltroCel]= useState("Todas")
  const [celulas,  setCelulas]  = useState([])
  const scrollRef = useRef(null)

  useEffect(() => {
    Promise.all([get("/gantt"), get("/celulas")]).then(([g,c]) => {
      setData(g); setCelulas(c); setLoading(false)
      // Scroll a hoy
      setTimeout(() => {
        if (scrollRef.current) {
          const hoy = new Date(g.hoy)
          const min = new Date(g.tareas.reduce((m,t) => t.fecha_ini < m ? t.fecha_ini : m, g.hoy))
          const px  = Math.round((hoy - min) / 86400000) * 28 - 200
          scrollRef.current.scrollLeft = Math.max(0, px)
        }
      }, 100)
    })
  }, [])

  if (loading) return <Spinner/>
  const { tareas, feriados, hoy } = data
  const ferSet = new Set(feriados)

  const tareasFiltradas = filtroCel === "Todas"
    ? tareas : tareas.filter(t => t.celula === filtroCel)

  if (!tareasFiltradas.length) return (
    <div className="space-y-4">
      <GanttHeader celulas={celulas} filtro={filtroCel} setFiltro={setFiltroCel}/>
      <div className="text-center py-16 text-slate-400">No hay órdenes con fecha para mostrar</div>
    </div>
  )

  // Rango de fechas
  const fechas = tareasFiltradas.flatMap(t => [t.fecha_ini, t.fecha_fin]).filter(Boolean)
  const fechaMinStr = fechas.reduce((m,f) => f < m ? f : m, fechas[0])
  const fechaMaxStr = fechas.reduce((m,f) => f > m ? f : m, fechas[0])
  const fechaMin = new Date(fechaMinStr + "T12:00:00")
  const fechaMax = new Date(fechaMaxStr + "T12:00:00")
  const nDias = Math.round((fechaMax - fechaMin) / 86400000) + 1

  // Generar columnas de días
  const dias = Array.from({length:nDias}, (_,i) => {
    const d = new Date(fechaMin); d.setDate(d.getDate() + i)
    return d
  })

  const hoyDate = new Date(hoy + "T12:00:00")
  const DOW = ["L","M","X","J","V","S","D"]

  return (
    <div className="space-y-4">
      <GanttHeader celulas={celulas} filtro={filtroCel} setFiltro={setFiltroCel}/>
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div ref={scrollRef} className="overflow-x-auto">
          <div style={{minWidth:`${200 + nDias*28}px`}}>
            {/* Header días */}
            <div className="flex border-b border-slate-200 bg-slate-50 sticky top-0 z-10">
              <div className="w-48 shrink-0 px-3 py-2 text-xs font-semibold text-slate-500 border-r border-slate-200">
                ORDEN
              </div>
              {dias.map((d,i) => {
                const isHoy    = d.toDateString() === hoyDate.toDateString()
                const isFer    = ferSet.has(d.toISOString().slice(0,10))
                const isDom    = d.getDay() === 0
                const isSab    = d.getDay() === 6
                return (
                  <div key={i} className={`w-7 shrink-0 flex flex-col items-center justify-center py-1 border-r text-center
                    ${isHoy ? "bg-amber-400 text-white font-bold" :
                      isFer  ? "bg-red-100 text-red-500" :
                      isDom  ? "bg-slate-100 text-slate-400" :
                      isSab  ? "bg-slate-50 text-slate-400" : "text-slate-500"}
                    border-slate-100`} style={{fontSize:"9px"}}>
                    <div>{DOW[d.getDay()===0?6:d.getDay()-1]}</div>
                    <div>{d.getDate()}</div>
                  </div>
                )
              })}
            </div>

            {/* Filas de tareas */}
            {tareasFiltradas.map((t, ti) => (
              <div key={t.id} className={`flex items-center border-b border-slate-100 ${ti%2===0?"bg-white":"bg-slate-50/50"}`}>
                {/* Info */}
                <div className="w-48 shrink-0 px-3 py-1.5 border-r border-slate-100">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{background:t.color}}/>
                    <span className="text-xs font-bold text-slate-700 truncate">{t.nro_ot}</span>
                    <span className="ml-auto"><Badge estado={t.estado}/></span>
                  </div>
                  <div className="text-xs text-slate-400 truncate pl-4">{t.sku} · {t.celula}</div>
                </div>
                {/* Barra */}
                <div className="flex-1 py-1.5 relative" style={{height:"42px"}}>
                  {t.fecha_ini && t.fecha_fin && (
                    <GanttBar tarea={t} dias={nDias} fechaMin={fechaMin}/>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function GanttHeader({ celulas, filtro, setFiltro }) {
  return (
    <div className="flex items-center justify-between">
      <h2 className="text-xl font-bold text-slate-800">GANTT</h2>
      <select value={filtro} onChange={e=>setFiltro(e.target.value)}
        className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        <option value="Todas">Todas las células</option>
        {celulas.filter(c=>c.activa).map(c=>(
          <option key={c.id} value={c.codigo}>{c.codigo} — {c.nombre}</option>
        ))}
      </select>
    </div>
  )
}

// ── ÓRDENES ──────────────────────────────────────────────────────────────────
function Ordenes({ isAdmin }) {
  const [ordenes,  setOrdenes]  = useState([])
  const [celulas,  setCelulas]  = useState([])
  const [skus,     setSkus]     = useState([])
  const [loading,  setLoading]  = useState(true)
  const [filtroC,  setFiltroC]  = useState("")
  const [filtroE,  setFiltroE]  = useState("")
  const [modal,    setModal]    = useState(null)  // null | "nueva" | orden
  const [avanceModal, setAvanceModal] = useState(null)
  const [msg,      setMsg]      = useState(null)

  const cargar = useCallback(() => {
    setLoading(true)
    Promise.all([get("/ordenes"), get("/celulas"), get("/skus")]).then(([o,c,s]) => {
      setOrdenes(o); setCelulas(c); setSkus(s); setLoading(false)
    })
  }, [])

  useEffect(() => { cargar() }, [cargar])

  const filtradas = ordenes.filter(o =>
    (filtroC === "" || o.celula_codigo === filtroC) &&
    (filtroE === "" || o.estado === filtroE)
  )

  async function cambiarEstado(oid, estado) {
    try {
      await put(`/ordenes/${oid}`, { estado })
      setMsg({ tipo:"ok", txt:`Estado actualizado a ${estado}` })
      cargar()
    } catch(e) { setMsg({ tipo:"err", txt:e.message }) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-xl font-bold text-slate-800">Órdenes de Trabajo</h2>
        <div className="flex gap-2 flex-wrap">
          <select value={filtroC} onChange={e=>setFiltroC(e.target.value)}
            className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">Todas las células</option>
            {celulas.filter(c=>c.activa).map(c=>(
              <option key={c.id} value={c.codigo}>{c.codigo}</option>
            ))}
          </select>
          <select value={filtroE} onChange={e=>setFiltroE(e.target.value)}
            className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">Todos los estados</option>
            {["Activa","Pendiente","Pausada","Completada"].map(e=>(
              <option key={e}>{e}</option>
            ))}
          </select>
          {isAdmin && (
            <button onClick={()=>setModal("nueva")}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-1.5 rounded-lg text-sm font-medium transition">
              + Nueva OT
            </button>
          )}
        </div>
      </div>

      {msg && <Alert tipo={msg.tipo==="ok"?"ok":"error"} msg={msg.txt} onClose={()=>setMsg(null)}/>}

      {loading ? <Spinner/> : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                {["N° OT","Célula","SKU","Cantidad","Producidas","Hs Rest.","F. Inicio","F. Fin","Días","Estado","",""].map(h=>(
                  <th key={h} className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtradas.map((o,i) => (
                <tr key={o.id} className={`border-b border-slate-100 ${i%2===0?"":"bg-slate-50/40"} hover:bg-blue-50/30`}>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full" style={{background:o.celula_color}}/>
                      <span className="font-mono font-bold text-slate-800">{o.nro_ot}</span>
                    </div>
                    {o.ot_precede_nro && (
                      <div className="text-xs text-purple-500 pl-3.5">→ {o.ot_precede_nro}</div>
                    )}
                  </td>
                  <td className="px-3 py-2 text-slate-600">{o.celula_codigo}</td>
                  <td className="px-3 py-2 text-slate-600">{o.sku_codigo}</td>
                  <td className="px-3 py-2 text-right font-mono">{o.cantidad?.toLocaleString()}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      <div className="h-1.5 w-16 bg-slate-200 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500 rounded-full"
                          style={{width:`${o.pct_avance}%`}}/>
                      </div>
                      <span className="text-xs text-slate-500">{o.pct_avance}%</span>
                    </div>
                    <div className="text-xs text-slate-400">{o.pzas_producidas?.toLocaleString()} pzas</div>
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-slate-600">{o.hs_restantes?.toFixed(1)}</td>
                  <td className="px-3 py-2 text-slate-600">
                    {fmtDate(o.fecha_inicio)}
                    {o.fecha_inicio_encadenada && <span className="text-green-500 text-xs ml-1">⛓</span>}
                  </td>
                  <td className="px-3 py-2 text-slate-600">{fmtDate(o.fecha_fin)}</td>
                  <td className={`px-3 py-2 text-right font-mono text-xs ${o.dias_residuales<=2&&o.estado!=="Completada"?"text-red-600 font-bold":""}`}>
                    {o.dias_residuales}d
                  </td>
                  <td className="px-3 py-2"><Badge estado={o.estado}/></td>
                  {isAdmin ? (
                    <>
                      <td className="px-2 py-2">
                        <button onClick={()=>setAvanceModal(o)}
                          className="text-xs bg-green-100 hover:bg-green-200 text-green-700 px-2 py-1 rounded transition">
                          +Avance
                        </button>
                      </td>
                      <td className="px-2 py-2">
                        <button onClick={()=>setModal(o)}
                          className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-2 py-1 rounded transition">
                          Editar
                        </button>
                      </td>
                    </>
                  ) : <td/> }
                </tr>
              ))}
            </tbody>
          </table>
          {filtradas.length === 0 && (
            <div className="text-center py-12 text-slate-400">No hay órdenes con esos filtros</div>
          )}
        </div>
      )}

      {modal && (
        <ModalOrden orden={modal==="nueva"?null:modal} celulas={celulas} skus={skus}
          ordenes={ordenes}
          onClose={()=>setModal(null)}
          onSave={()=>{ setModal(null); cargar(); setMsg({tipo:"ok",txt:"Guardado"}) }}
          onMsg={setMsg}/>
      )}
      {avanceModal && (
        <ModalAvance orden={avanceModal}
          onClose={()=>setAvanceModal(null)}
          onSave={()=>{ setAvanceModal(null); cargar(); setMsg({tipo:"ok",txt:"Avance cargado"}) }}
          onMsg={setMsg}/>
      )}
    </div>
  )
}

function ModalOrden({ orden, celulas, skus, ordenes, onClose, onSave, onMsg }) {
  const [form, setForm] = useState({
    nro_ot:          orden?.nro_ot         ?? "",
    celula_id:       orden?.celula_id      ?? "",
    sku_id:          orden?.sku_id         ?? "",
    cantidad:        orden?.cantidad       ?? "",
    fecha_inicio:    orden?.fecha_inicio   ?? "",
    estado:          orden?.estado         ?? "Pendiente",
    ot_precede_id:   orden?.ot_precede_id  ?? "",
    notas:           orden?.notas          ?? "",
  })
  const [saving, setSaving] = useState(false)

  async function guardar() {
    setSaving(true)
    try {
      const body = {
        nro_ot: form.nro_ot, celula_id: Number(form.celula_id),
        sku_id: Number(form.sku_id), cantidad: Number(form.cantidad),
        fecha_inicio: form.fecha_inicio || null, estado: form.estado,
        ot_precede_id: form.ot_precede_id ? Number(form.ot_precede_id) : null,
        notas: form.notas || null,
      }
      if (orden) await put(`/ordenes/${orden.id}`, body)
      else       await post("/ordenes", body)
      onSave()
    } catch(e) { onMsg({tipo:"err", txt:e.message}); setSaving(false) }
  }

  const inp = "w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"

  return (
    <Modal title={orden ? `Editar ${orden.nro_ot}` : "Nueva OT"} onClose={onClose}>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">N° OT</label>
          <input className={inp} value={form.nro_ot} onChange={e=>setForm(f=>({...f,nro_ot:e.target.value}))} disabled={!!orden}/>
        </div>
        <div>
          <label className="label">Célula</label>
          <select className={inp} value={form.celula_id} onChange={e=>setForm(f=>({...f,celula_id:e.target.value}))}>
            <option value="">— Seleccionar —</option>
            {celulas.filter(c=>c.activa).map(c=><option key={c.id} value={c.id}>{c.codigo} — {c.nombre}</option>)}
          </select>
        </div>
        <div>
          <label className="label">SKU</label>
          <select className={inp} value={form.sku_id} onChange={e=>setForm(f=>({...f,sku_id:e.target.value}))}>
            <option value="">— Seleccionar —</option>
            {skus.map(s=><option key={s.id} value={s.id}>{s.codigo} — {s.descripcion}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Cantidad</label>
          <input type="number" className={inp} value={form.cantidad} onChange={e=>setForm(f=>({...f,cantidad:e.target.value}))}/>
        </div>
        <div>
          <label className="label">Fecha inicio <span className="text-slate-400">(dejar vacío si encadenada)</span></label>
          <input type="date" className={inp} value={form.fecha_inicio} onChange={e=>setForm(f=>({...f,fecha_inicio:e.target.value}))}/>
        </div>
        <div>
          <label className="label">Estado</label>
          <select className={inp} value={form.estado} onChange={e=>setForm(f=>({...f,estado:e.target.value}))}>
            {["Pendiente","Activa","Pausada","Completada"].map(e=><option key={e}>{e}</option>)}
          </select>
        </div>
        <div>
          <label className="label">OT Precede <span className="text-slate-400">(encadenamiento)</span></label>
          <select className={inp} value={form.ot_precede_id} onChange={e=>setForm(f=>({...f,ot_precede_id:e.target.value}))}>
            <option value="">— Ninguna —</option>
            {ordenes.filter(o=>o.id!==orden?.id).map(o=><option key={o.id} value={o.id}>{o.nro_ot}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Notas</label>
          <input className={inp} value={form.notas} onChange={e=>setForm(f=>({...f,notas:e.target.value}))}/>
        </div>
      </div>
      <div className="flex justify-end gap-3 mt-6">
        <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg">Cancelar</button>
        <button onClick={guardar} disabled={saving}
          className="px-6 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg disabled:opacity-60">
          {saving ? "Guardando…" : "Guardar"}
        </button>
      </div>
    </Modal>
  )
}

function ModalAvance({ orden, onClose, onSave, onMsg }) {
  const [form, setForm] = useState({ fecha:new Date().toISOString().slice(0,10),
                                     turno_1:"", turno_2:"0", turno_3:"0", scrap:"0", notas:"" })
  const [historial, setHistorial] = useState([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    get(`/avance/${orden.id}`).then(setHistorial)
  }, [orden.id])

  async function guardar() {
    setSaving(true)
    try {
      await post("/avance", {
        orden_id: orden.id, fecha: form.fecha,
        turno_1: Number(form.turno_1)||0, turno_2: Number(form.turno_2)||0,
        turno_3: Number(form.turno_3)||0, scrap: Number(form.scrap)||0,
        notas: form.notas || null,
      })
      onSave()
    } catch(e) { onMsg({tipo:"err",txt:e.message}); setSaving(false) }
  }

  const inp = "w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
  const total = (Number(form.turno_1)||0)+(Number(form.turno_2)||0)+(Number(form.turno_3)||0)-(Number(form.scrap)||0)

  return (
    <Modal title={`Cargar avance — ${orden.nro_ot}`} onClose={onClose} wide>
      <div className="grid grid-cols-2 gap-6">
        {/* Formulario */}
        <div className="space-y-3">
          <div className="bg-slate-50 rounded-lg p-3 text-sm">
            <div className="grid grid-cols-3 gap-2 text-center">
              <div><div className="text-slate-400 text-xs">Total</div><div className="font-bold">{orden.cantidad?.toLocaleString()}</div></div>
              <div><div className="text-slate-400 text-xs">Producidas</div><div className="font-bold text-green-600">{orden.pzas_producidas?.toLocaleString()}</div></div>
              <div><div className="text-slate-400 text-xs">Restantes</div><div className="font-bold text-blue-600">{orden.pzas_restantes?.toLocaleString()}</div></div>
            </div>
          </div>
          <div>
            <label className="label">Fecha</label>
            <input type="date" className={inp} value={form.fecha} onChange={e=>setForm(f=>({...f,fecha:e.target.value}))}/>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {["turno_1","turno_2","turno_3"].map((t,i)=>(
              <div key={t}>
                <label className="label">Turno {i+1}</label>
                <input type="number" className={inp} value={form[t]} onChange={e=>setForm(f=>({...f,[t]:e.target.value}))}/>
              </div>
            ))}
          </div>
          <div>
            <label className="label">Scrap</label>
            <input type="number" className={inp} value={form.scrap} onChange={e=>setForm(f=>({...f,scrap:e.target.value}))}/>
          </div>
          <div className="bg-green-50 rounded-lg p-2 text-center">
            <div className="text-xs text-green-600">Total buenas esta carga</div>
            <div className="text-2xl font-bold text-green-700">{total}</div>
          </div>
          <div>
            <label className="label">Notas</label>
            <input className={inp} value={form.notas} onChange={e=>setForm(f=>({...f,notas:e.target.value}))}/>
          </div>
          <div className="flex gap-3">
            <button onClick={onClose} className="flex-1 py-2 text-sm text-slate-600 border border-slate-300 rounded-lg hover:bg-slate-50">Cancelar</button>
            <button onClick={guardar} disabled={saving}
              className="flex-1 py-2 text-sm bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg disabled:opacity-60">
              {saving ? "Guardando…" : "Cargar"}
            </button>
          </div>
        </div>
        {/* Historial */}
        <div>
          <div className="text-sm font-semibold text-slate-600 mb-2">Historial de carga</div>
          <div className="space-y-1.5 max-h-80 overflow-y-auto">
            {historial.length===0 && <div className="text-xs text-slate-400 py-4 text-center">Sin cargas previas</div>}
            {historial.map(h=>(
              <div key={h.id} className="bg-slate-50 rounded-lg p-2 text-xs">
                <div className="flex justify-between">
                  <span className="font-semibold">{fmtDateFull(h.fecha)}</span>
                  <span className="text-green-600 font-bold">{h.acumulado?.toLocaleString()} pzas ({h.pct}%)</span>
                </div>
                <div className="text-slate-500">T1:{h.turno_1} T2:{h.turno_2} T3:{h.turno_3} Scrap:{h.scrap} · {h.usuario}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Modal>
  )
}

// ── CONFIGURACIÓN ────────────────────────────────────────────────────────────
function Configuracion() {
  const [tab, setTab] = useState("celulas")
  const [celulas, setCelulas] = useState([])
  const [skus,    setSkus]    = useState([])
  const [feriados,setFeriados]= useState([])
  const [usuarios,setUsuarios]= useState([])
  const [loading, setLoading] = useState(true)
  const [editC,   setEditC]   = useState(null)
  const [msg,     setMsg]     = useState(null)

  useEffect(()=>{
    Promise.all([get("/celulas"),get("/skus"),get("/feriados"),get("/auth/usuarios")]).then(([c,s,f,u])=>{
      setCelulas(c);setSkus(s);setFeriados(f);setUsuarios(u);setLoading(false)
    })
  },[])

  if(loading) return <Spinner/>
  const tabs=[{k:"celulas",l:"Células"},{k:"skus",l:"SKUs"},{k:"feriados",l:"Feriados"},{k:"usuarios",l:"Usuarios"}]

  return(
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-slate-800">Configuración</h2>
      <div className="flex gap-1 bg-slate-100 p-1 rounded-xl w-fit">
        {tabs.map(t=>(
          <button key={t.k} onClick={()=>setTab(t.k)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${tab===t.k?"bg-white shadow text-slate-800":"text-slate-500 hover:text-slate-700"}`}>
            {t.l}
          </button>
        ))}
      </div>
      {msg && <Alert tipo={msg.tipo==="ok"?"ok":"error"} msg={msg.txt} onClose={()=>setMsg(null)}/>}
      {tab==="celulas" && <TabCelulas celulas={celulas} onEdit={setEditC}/>}
      {tab==="skus"    && <TabSKUs    skus={skus} setSkus={setSkus} setMsg={setMsg}/>}
      {tab==="feriados"&& <TabFeriados feriados={feriados} setFeriados={setFeriados} setMsg={setMsg}/>}
      {tab==="usuarios"&& <TabUsuarios usuarios={usuarios} setUsuarios={setUsuarios} setMsg={setMsg}/>}
      {editC && <ModalCelula celula={editC==="nueva"?null:editC}
        onClose={()=>setEditC(null)}
        onSave={async(data)=>{
          try{
            if(editC==="nueva") await post("/celulas",data)
            else await put(`/celulas/${editC.id}`,data)
            const c=await get("/celulas"); setCelulas(c)
            setMsg({tipo:"ok",txt:"Célula guardada"}); setEditC(null)
          }catch(e){setMsg({tipo:"err",txt:e.message})}
        }}/>}
    </div>
  )
}

function TabCelulas({celulas,onEdit}){
  return(
    <div>
      <div className="flex justify-end mb-3">
        <button onClick={()=>onEdit("nueva")} className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded-lg hover:bg-blue-700">+ Nueva célula</button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {celulas.map(c=>(
          <div key={c.id} className={`bg-white border rounded-xl p-4 ${!c.activa?"opacity-50":""}`}>
            <div className="flex items-center gap-2 mb-2">
              <span className="w-3 h-3 rounded-full" style={{background:c.color_hex}}/>
              <span className="font-bold text-slate-800">{c.codigo}</span>
              <span className="text-xs text-slate-400">{c.nombre}</span>
              <span className={`ml-auto text-xs px-2 py-0.5 rounded-full ${c.activa?"bg-green-100 text-green-600":"bg-slate-100 text-slate-400"}`}>
                {c.activa?"Activa":"Futura"}
              </span>
            </div>
            <div className="text-xs text-slate-500 grid grid-cols-2 gap-1">
              <span>L–V: {c.turnos_lv}t × {c.hs_turno_lv}hs ({c.efic_lv}%)</span>
              <span>Sáb: {c.turnos_sab}t × {c.hs_turno_sab}hs ({c.efic_sab}%)</span>
            </div>
            <button onClick={()=>onEdit(c)} className="mt-2 text-xs text-blue-600 hover:underline">Editar</button>
          </div>
        ))}
      </div>
    </div>
  )
}

function TabSKUs({skus,setSkus,setMsg}){
  const [form,setForm]=useState({codigo:"",descripcion:"",material:"",proceso:"",t_unit_min:""})
  async function agregar(){
    try{
      await post("/skus",{...form,t_unit_min:Number(form.t_unit_min),activo:true})
      const s=await get("/skus"); setSkus(s)
      setMsg({tipo:"ok",txt:"SKU agregado"})
      setForm({codigo:"",descripcion:"",material:"",proceso:"",t_unit_min:""})
    }catch(e){setMsg({tipo:"err",txt:e.message})}
  }
  const inp="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
  return(
    <div className="space-y-4">
      <div className="bg-slate-50 rounded-xl p-4 flex gap-2 flex-wrap items-end">
        <div><label className="label text-xs">Código</label><input className={inp} value={form.codigo} onChange={e=>setForm(f=>({...f,codigo:e.target.value}))}/></div>
        <div><label className="label text-xs">Descripción</label><input className={inp+" w-48"} value={form.descripcion} onChange={e=>setForm(f=>({...f,descripcion:e.target.value}))}/></div>
        <div><label className="label text-xs">T.unit (min/pza)</label><input type="number" step="0.001" className={inp+" w-32"} value={form.t_unit_min} onChange={e=>setForm(f=>({...f,t_unit_min:e.target.value}))}/></div>
        <button onClick={agregar} className="bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-blue-700">Agregar</button>
      </div>
      <table className="w-full text-sm bg-white border border-slate-200 rounded-xl overflow-hidden">
        <thead><tr className="bg-slate-50 border-b">{["Código","Descripción","Material","Proceso","T.unit min/pza"].map(h=><th key={h} className="px-3 py-2 text-left text-xs text-slate-500">{h}</th>)}</tr></thead>
        <tbody>
          {skus.map((s,i)=>(
            <tr key={s.id} className={i%2===0?"":"bg-slate-50/40"}>
              <td className="px-3 py-2 font-mono font-bold text-blue-700">{s.codigo}</td>
              <td className="px-3 py-2 text-slate-600">{s.descripcion}</td>
              <td className="px-3 py-2 text-slate-500">{s.material}</td>
              <td className="px-3 py-2 text-slate-500">{s.proceso}</td>
              <td className="px-3 py-2 text-right font-mono text-orange-600 font-bold">{s.t_unit_min?.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TabFeriados({feriados,setFeriados,setMsg}){
  const [fecha,setFecha]=useState(""); const [desc,setDesc]=useState("")
  async function agregar(){
    try{
      await post("/feriados",{fecha,descripcion:desc||null})
      const f=await get("/feriados"); setFeriados(f)
      setMsg({tipo:"ok",txt:"Feriado agregado"}); setFecha(""); setDesc("")
    }catch(e){setMsg({tipo:"err",txt:e.message})}
  }
  async function eliminar(id){
    try{ await del(`/feriados/${id}`); setFeriados(f=>f.filter(x=>x.id!==id)) }
    catch(e){ setMsg({tipo:"err",txt:e.message}) }
  }
  return(
    <div className="space-y-4">
      <div className="bg-slate-50 rounded-xl p-4 flex gap-2 items-end">
        <div><label className="label text-xs">Fecha</label>
          <input type="date" className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm" value={fecha} onChange={e=>setFecha(e.target.value)}/></div>
        <div><label className="label text-xs">Descripción</label>
          <input className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm w-48" value={desc} onChange={e=>setDesc(e.target.value)}/></div>
        <button onClick={agregar} className="bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-blue-700">Agregar</button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
        {feriados.map(f=>(
          <div key={f.id} className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 flex justify-between items-center">
            <div>
              <div className="text-sm font-semibold text-red-700">{fmtDateFull(f.fecha)}</div>
              <div className="text-xs text-red-500">{f.descripcion}</div>
            </div>
            <button onClick={()=>eliminar(f.id)} className="text-red-400 hover:text-red-600 text-lg">×</button>
          </div>
        ))}
      </div>
    </div>
  )
}

function TabUsuarios({usuarios,setUsuarios,setMsg}){
  const [form,setForm]=useState({nombre:"",email:"",password:"",rol:"operario"})
  async function agregar(){
    try{
      await post("/auth/usuarios",form)
      const u=await get("/auth/usuarios"); setUsuarios(u)
      setMsg({tipo:"ok",txt:"Usuario creado"})
      setForm({nombre:"",email:"",password:"",rol:"operario"})
    }catch(e){setMsg({tipo:"err",txt:e.message})}
  }
  const inp="border border-slate-300 rounded-lg px-3 py-1.5 text-sm"
  return(
    <div className="space-y-4">
      <div className="bg-slate-50 rounded-xl p-4 flex gap-2 flex-wrap items-end">
        <div><label className="label text-xs">Nombre</label><input className={inp} value={form.nombre} onChange={e=>setForm(f=>({...f,nombre:e.target.value}))}/></div>
        <div><label className="label text-xs">Email</label><input type="email" className={inp} value={form.email} onChange={e=>setForm(f=>({...f,email:e.target.value}))}/></div>
        <div><label className="label text-xs">Contraseña</label><input type="password" className={inp} value={form.password} onChange={e=>setForm(f=>({...f,password:e.target.value}))}/></div>
        <div><label className="label text-xs">Rol</label>
          <select className={inp} value={form.rol} onChange={e=>setForm(f=>({...f,rol:e.target.value}))}>
            <option value="operario">Operario (solo lectura)</option>
            <option value="admin">Admin (edición completa)</option>
          </select>
        </div>
        <button onClick={agregar} className="bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-blue-700">Crear usuario</button>
      </div>
      <table className="w-full text-sm bg-white border border-slate-200 rounded-xl overflow-hidden">
        <thead><tr className="bg-slate-50 border-b">{["Nombre","Email","Rol","Estado"].map(h=><th key={h} className="px-3 py-2 text-left text-xs text-slate-500">{h}</th>)}</tr></thead>
        <tbody>
          {usuarios.map((u,i)=>(
            <tr key={u.id} className={i%2===0?"":"bg-slate-50/40"}>
              <td className="px-3 py-2 font-medium">{u.nombre}</td>
              <td className="px-3 py-2 text-slate-500">{u.email}</td>
              <td className="px-3 py-2"><span className={`text-xs px-2 py-0.5 rounded-full ${u.rol==="admin"?"bg-purple-100 text-purple-700":"bg-slate-100 text-slate-600"}`}>{u.rol}</span></td>
              <td className="px-3 py-2"><span className={`text-xs ${u.activo?"text-green-600":"text-red-500"}`}>{u.activo?"Activo":"Inactivo"}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ModalCelula({celula,onClose,onSave}){
  const [form,setForm]=useState({
    codigo:celula?.codigo??"",nombre:celula?.nombre??"",
    turnos_lv:celula?.turnos_lv??1,hs_turno_lv:celula?.hs_turno_lv??8,
    turnos_sab:celula?.turnos_sab??3,hs_turno_sab:celula?.hs_turno_sab??4,
    efic_lv:celula?.efic_lv??85,efic_sab:celula?.efic_sab??85,
    hs_extra_lv:celula?.hs_extra_lv??0,hs_extra_sab:celula?.hs_extra_sab??0,
    hs_extra_dom:celula?.hs_extra_dom??0,hs_extra_fer:celula?.hs_extra_fer??0,
    activa:celula?.activa??true,color_hex:celula?.color_hex??"#94A3B8",
  })
  const inp="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
  return(
    <Modal title={celula?"Editar célula":"Nueva célula"} onClose={onClose}>
      <div className="grid grid-cols-2 gap-4">
        <div><label className="label">Código</label><input className={inp} value={form.codigo} onChange={e=>setForm(f=>({...f,codigo:e.target.value}))} disabled={!!celula}/></div>
        <div><label className="label">Nombre</label><input className={inp} value={form.nombre} onChange={e=>setForm(f=>({...f,nombre:e.target.value}))}/></div>
        <div><label className="label">Turnos L–V</label><input type="number" className={inp} value={form.turnos_lv} onChange={e=>setForm(f=>({...f,turnos_lv:Number(e.target.value)}))}/></div>
        <div><label className="label">Hs/turno L–V</label><input type="number" step="0.5" className={inp} value={form.hs_turno_lv} onChange={e=>setForm(f=>({...f,hs_turno_lv:Number(e.target.value)}))}/></div>
        <div><label className="label">Turnos Sáb</label><input type="number" className={inp} value={form.turnos_sab} onChange={e=>setForm(f=>({...f,turnos_sab:Number(e.target.value)}))}/></div>
        <div><label className="label">Hs/turno Sáb</label><input type="number" step="0.5" className={inp} value={form.hs_turno_sab} onChange={e=>setForm(f=>({...f,hs_turno_sab:Number(e.target.value)}))}/></div>
        <div><label className="label">Eficiencia L–V %</label><input type="number" className={inp} value={form.efic_lv} onChange={e=>setForm(f=>({...f,efic_lv:Number(e.target.value)}))}/></div>
        <div><label className="label">Eficiencia Sáb %</label><input type="number" className={inp} value={form.efic_sab} onChange={e=>setForm(f=>({...f,efic_sab:Number(e.target.value)}))}/></div>
        <div><label className="label">Color (hex)</label>
          <div className="flex gap-2">
            <input type="color" value={form.color_hex} onChange={e=>setForm(f=>({...f,color_hex:e.target.value}))} className="h-9 w-14 rounded border border-slate-300"/>
            <input className={inp} value={form.color_hex} onChange={e=>setForm(f=>({...f,color_hex:e.target.value}))}/>
          </div>
        </div>
        <div className="flex items-center gap-2 pt-5">
          <input type="checkbox" checked={form.activa} onChange={e=>setForm(f=>({...f,activa:e.target.checked}))} className="w-4 h-4"/>
          <label className="text-sm text-slate-700">Activa</label>
        </div>
      </div>
      <div className="flex justify-end gap-3 mt-6">
        <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg">Cancelar</button>
        <button onClick={()=>onSave(form)} className="px-6 py-2 text-sm bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700">Guardar</button>
      </div>
    </Modal>
  )
}

// ── AUDIT LOG ────────────────────────────────────────────────────────────────
function AuditLog() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  useEffect(()=>{ get("/audit?limite=200").then(d=>{setLogs(d);setLoading(false)}) },[])
  if(loading) return <Spinner/>
  const ACCION_CLR={CREATE:"bg-green-100 text-green-700",UPDATE:"bg-blue-100 text-blue-700",
                    DELETE:"bg-red-100 text-red-700",ARCHIVE:"bg-purple-100 text-purple-700"}
  return(
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-slate-800">Registro de actividad</h2>
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-slate-50 border-b">
            {["Timestamp","Usuario","Tabla","Acción","Detalle"].map(h=><th key={h} className="px-3 py-2 text-left text-xs text-slate-500">{h}</th>)}
          </tr></thead>
          <tbody>
            {logs.map((l,i)=>(
              <tr key={l.id} className={`border-b border-slate-50 ${i%2===0?"":"bg-slate-50/40"}`}>
                <td className="px-3 py-2 text-xs text-slate-400 whitespace-nowrap">
                  {new Date(l.timestamp).toLocaleString("es-AR")}
                </td>
                <td className="px-3 py-2 font-medium text-slate-700">{l.usuario}</td>
                <td className="px-3 py-2 font-mono text-xs text-slate-500">{l.tabla}</td>
                <td className="px-3 py-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${ACCION_CLR[l.accion]||"bg-slate-100 text-slate-600"}`}>
                    {l.accion}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs text-slate-400 max-w-xs truncate">{l.detalle}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── MODAL BASE ────────────────────────────────────────────────────────────────
function Modal({ title, children, onClose, wide }) {
  return(
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className={`bg-white rounded-2xl shadow-2xl w-full ${wide?"max-w-3xl":"max-w-lg"} max-h-[90vh] overflow-y-auto`}>
        <div className="flex items-center justify-between p-5 border-b border-slate-200">
          <h3 className="font-bold text-slate-800">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl">✕</button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}

// ── APP ───────────────────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { key:"dashboard", label:"Dashboard", icon:"📊" },
  { key:"gantt",     label:"GANTT",     icon:"📅" },
  { key:"ordenes",   label:"Órdenes",   icon:"📋" },
  { key:"config",    label:"Config",    icon:"⚙️",  adminOnly:true },
  { key:"audit",     label:"Actividad", icon:"🔍",  adminOnly:true },
]

export default function App() {
  const [user,  setUser]  = useState(() => {
    const t = localStorage.getItem("token")
    const r = localStorage.getItem("rol")
    const n = localStorage.getItem("nombre")
    return t ? { token:t, rol:r, nombre:n } : null
  })
  const [page, setPage]  = useState("dashboard")

  if (!user) return <Login onLogin={setUser}/>

  const isAdmin = user.rol === "admin"

  function logout() {
    localStorage.clear(); setUser(null)
  }

  const visibleNav = NAV_ITEMS.filter(n => !n.adminOnly || isAdmin)

  return(
    <div className="min-h-screen bg-slate-50 flex">
      {/* Sidebar */}
      <aside className="w-56 bg-slate-900 flex flex-col shrink-0">
        <div className="p-5 border-b border-slate-700">
          <div className="text-white font-bold text-lg">🏭 ERP Forja</div>
          <div className="text-slate-400 text-xs mt-0.5">Sistema de producción</div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {visibleNav.map(n=>(
            <button key={n.key} onClick={()=>setPage(n.key)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition
                ${page===n.key
                  ? "bg-blue-600 text-white font-medium"
                  : "text-slate-400 hover:bg-slate-800 hover:text-white"}`}>
              <span>{n.icon}</span>
              <span>{n.label}</span>
            </button>
          ))}
        </nav>
        <div className="p-3 border-t border-slate-700">
          <div className="px-3 py-2 text-xs text-slate-400">
            <div className="font-medium text-slate-300">{user.nombre}</div>
            <div>{user.rol === "admin" ? "Administrador" : "Operario"}</div>
          </div>
          <button onClick={logout}
            className="w-full text-left px-3 py-2 text-xs text-slate-500 hover:text-red-400 transition">
            ← Cerrar sesión
          </button>
        </div>
      </aside>

      {/* Contenido */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto p-6">
          {page==="dashboard" && <Dashboard/>}
          {page==="gantt"     && <Gantt/>}
          {page==="ordenes"   && <Ordenes isAdmin={isAdmin}/>}
          {page==="config"    && isAdmin && <Configuracion/>}
          {page==="audit"     && isAdmin && <AuditLog/>}
        </div>
      </main>
    </div>
  )
}
