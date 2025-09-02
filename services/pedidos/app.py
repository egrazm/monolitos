
import os, sqlite3, logging, datetime
from functools import wraps
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("SERVICE_TOKEN", "penguin-secret")
PORT = int(os.getenv("PORT", "5000"))
DB_PATH = os.getenv("DB_PATH", "service.db")

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs.log", encoding="utf-8")
    ]
)
log = logging.getLogger(__name__)

def require_token(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {TOKEN}":
            return jsonify({"error": "No autorizado"}), 401
        return fn(*args, **kwargs)
    return wrapper

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/health")
def health():
    return {"status": "ok", "service": os.path.basename(os.getcwd())}

import requests, time
from http_client import call_json
from flask import request, jsonify

PRODUCTS_URL = os.getenv("PRODUCTS_URL", "http://127.0.0.1:5001")
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://127.0.0.1:5002")
PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://127.0.0.1:5003")

def init_db():
    with get_db() as con:
        c = con.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total REAL NOT NULL,
                estado TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER NOT NULL,
                producto_id INTEGER NOT NULL,
                cantidad INTEGER NOT NULL,
                precio_unit REAL NOT NULL
            )
        """)
        con.commit()

def _get_producto(pid):
    url = f"{PRODUCTS_URL}/productos/{pid}"
    r = call_json("productos", "GET", url)
    if r.status_code != 200:
        raise RuntimeError(f"Producto {pid} no encontrado")
    return r.json()

def _reservar(pid, cantidad):
    url = f"{INVENTORY_URL}/reservar"
    r = call_json("inventario", "POST", url, json={"producto_id": pid, "cantidad": cantidad})
    if r.status_code != 200:
        return None, r.json()
    return r.json()["reserva_id"], None

def _liberar(reserva_id):
    url = f"{INVENTORY_URL}/liberar"
    call_json("inventario", "POST", url, json={"reserva_id": reserva_id})

def _consumir(reserva_id):
    url = f"{INVENTORY_URL}/consumir"
    call_json("inventario", "POST", url, json={"reserva_id": reserva_id})

def _pagar(monto, moneda, medio, referencia=None, fail=False):
    url = f"{PAYMENTS_URL}/pagar"
    body = {"monto": monto, "moneda": moneda, "medio": medio}
    if referencia: body["referencia"] = referencia
    if fail: body["fail"] = True
    r = call_json("pagos", "POST", url, json=body)
    return r.json()

@app.post("/pedidos")
@require_token
def crear_pedido():
    data = request.get_json(force=True)
    items = data.get("items") or []
    pago = data.get("pago") or {}

    if not items:
        return {"error":"Debes enviar items"}, 400

    # 1) Precios de productos
    detalle = []
    total = 0.0
    for it in items:
        pid = int(it.get("producto_id"))
        cant = int(it.get("cantidad"))
        if pid <= 0 or cant <= 0:
            return {"error":"Items inválidos"}, 400
        prod = _get_producto(pid)
        precio_unit = float(prod["precio"])
        total += precio_unit * cant
        detalle.append({"producto_id": pid, "cantidad": cant, "precio_unit": precio_unit})

    # 2) Reservar stock
    reservas = []
    try:
        for d in detalle:
            rid, err = _reservar(d["producto_id"], d["cantidad"])
            if not rid:
                # si falla una reserva, liberar lo reservado antes y abortar
                for rr in reservas:
                    _liberar(rr)
                return {"error": "No se pudo reservar", "detalle": err}, 409
            reservas.append(rid)

        # 3) Intentar pago
        medio = (pago.get("medio") or "tarjeta")
        moneda = (pago.get("moneda") or "PYG")
        fail = bool(pago.get("fail", False))
        p = _pagar(total, moneda, medio, referencia=None, fail=fail)

        if p.get("estado") != "aprobado":
            # pago rechazado -> liberar reservas
            for rr in reservas:
                _liberar(rr)
            estado = "cancelado"
        else:
            # consumo de reservas (confirmar)
            for rr in reservas:
                _consumir(rr)
            estado = "confirmado"

        # 4) Persistir pedido
        with get_db() as con:
            c = con.cursor()
            c.execute("INSERT INTO pedidos (total, estado, created_at) VALUES (?,?,?)",
                      (total, estado, datetime.datetime.utcnow().isoformat()))
            pedido_id = c.lastrowid
            for d in detalle:
                c.execute("INSERT INTO items (pedido_id, producto_id, cantidad, precio_unit) VALUES (?,?,?,?)",
                          (pedido_id, d["producto_id"], d["cantidad"], d["precio_unit"]))
            con.commit()

        return {"pedido_id": pedido_id, "total": total, "estado": estado, "pago": p}, (201 if estado=="confirmado" else 202)

    except Exception as e:
        # Falla inesperada -> liberar reservas best-effort
        for rr in reservas:
            try: _liberar(rr)
            except: pass
        log.exception("Error creando pedido")
        return {"error": "Fallo interno creando pedido", "detalle": str(e)}, 500

@app.get("/pedidos")
@require_token
def listar_pedidos():
    with get_db() as con:
        c = con.cursor()
        rows = c.execute("SELECT id, total, estado, created_at FROM pedidos ORDER BY id DESC").fetchall()
    return {"items": [dict(r) for r in rows]}

@app.get("/pedidos/<int:pid>")
@require_token
def detalle_pedido(pid):
    with get_db() as con:
        c = con.cursor()
        p = c.execute("SELECT id, total, estado, created_at FROM pedidos WHERE id=?", (pid,)).fetchone()
        if not p: return {"error":"No encontrado"}, 404
        its = c.execute("SELECT producto_id, cantidad, precio_unit FROM items WHERE pedido_id=?", (pid,)).fetchall()
    return {"pedido": dict(p), "items": [dict(x) for x in its]}

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT, debug=True)
