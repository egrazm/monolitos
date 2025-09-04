import os, sqlite3, logging, datetime
from functools import wraps
from flask import Flask, request, jsonify
from dotenv import load_dotenv

import requests

load_dotenv()

TOKEN = os.getenv("SERVICE_TOKEN", "penguin-secret")
PORT = int(os.getenv("PORT", "5003"))
DB_PATH = os.getenv("DB_PATH", "pedidos.db")   

PRODUCTS_URL  = os.getenv("PRODUCTS_URL",  "http://127.0.0.1:5001")
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://127.0.0.1:5002")
PAYMENTS_URL  = os.getenv("PAYMENTS_URL",  "http://127.0.0.1:5004") 

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
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

def auth_headers():
    return {"Authorization": f"Bearer {TOKEN}"}

@app.get("/health")
def health():
    return {"status": "ok", "service": "pedidos"}

@app.post("/pedidos")
@require_token
def crear_pedido():
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    pago = data.get("pago") or {}

    if not items:
        return {"error": "Debes enviar items"}, 400

    detalle = []
    total = 0.0
    for it in items:
        try:
            producto_id = int(it.get("producto_id"))
            cantidad = int(it.get("cantidad"))
        except (TypeError, ValueError):
            return {"error": "Items inválidos"}, 400
        if producto_id <= 0 or cantidad <= 0:
            return {"error": "Items inválidos"}, 400

        r = requests.get(f"{PRODUCTS_URL}/productos/{producto_id}", headers=auth_headers(), timeout=5)
        if r.status_code != 200:
            return {"error": f"Producto {producto_id} no encontrado"}, 400
        prod = r.json()
        precio_unit = float(prod.get("precio", 0))
        if precio_unit <= 0:
            return {"error": f"Precio inválido para producto {producto_id}"}, 400

        total += precio_unit * cantidad
        detalle.append({"producto_id": producto_id, "cantidad": cantidad, "precio_unit": precio_unit})

    reservas = []
    try:
        for d in detalle:
            r = requests.post(f"{INVENTORY_URL}/reservar", headers=auth_headers(),
                              json={"producto_id": d["producto_id"], "cantidad": d["cantidad"]}, timeout=5)
            if r.status_code != 200:
                for rr in reservas:
                    try:
                        requests.post(f"{INVENTORY_URL}/liberar", headers=auth_headers(), json={"reserva_id": rr}, timeout=5)
                    except Exception:
                        log.exception("Error liberando reserva %s", rr)
                return {"error": "No se pudo reservar", "detalle": r.json()}, 409
            reservas.append(r.json()["reserva_id"])

        medio = pago.get("medio", "tarjeta")
        moneda = pago.get("moneda", "PYG")
        referencia = pago.get("referencia")
        pay_body = {"monto": total, "moneda": moneda, "medio": medio}
        if referencia:
            pay_body["referencia"] = referencia
        pay_resp = requests.post(f"{PAYMENTS_URL}/pagar", headers=auth_headers(), json=pay_body, timeout=5)
        if pay_resp.status_code != 200 or pay_resp.json().get("estado") != "aprobado":
            for rr in reservas:
                try:
                    requests.post(f"{INVENTORY_URL}/liberar", headers=auth_headers(), json={"reserva_id": rr}, timeout=5)
                except Exception:
                    log.exception("Error liberando reserva %s", rr)
            estado = "cancelado"
        else:
            for rr in reservas:
                requests.post(f"{INVENTORY_URL}/consumir", headers=auth_headers(), json={"reserva_id": rr}, timeout=5)
            estado = "confirmado"

        with get_db() as con:
            c = con.cursor()
            c.execute("INSERT INTO pedidos (total, estado, created_at) VALUES (?,?,?)",
                      (total, estado, datetime.datetime.utcnow().isoformat()))
            pedido_id = c.lastrowid
            for d in detalle:
                c.execute("INSERT INTO items (pedido_id, producto_id, cantidad, precio_unit) VALUES (?,?,?,?)",
                          (pedido_id, d["producto_id"], d["cantidad"], d["precio_unit"]))
            con.commit()

        code = 201 if estado == "confirmado" else 202
        return {"pedido_id": pedido_id, "total": total, "estado": estado}, code

    except requests.RequestException as e:
        log.exception("Error en comunicación interna: %s", e)
        for rr in reservas:
            try:
                requests.post(f"{INVENTORY_URL}/liberar", headers=auth_headers(), json={"reserva_id": rr}, timeout=5)
            except Exception:
                log.exception("Error liberando reserva %s", rr)
        return {"error": "Fallo comunicando con servicios internos"}, 502

@app.get("/pedidos/<int:pid>")
@require_token
def detalle_pedido(pid: int):
    with get_db() as con:
        c = con.cursor()
        p = c.execute("SELECT id, total, estado, created_at FROM pedidos WHERE id=?", (pid,)).fetchone()
        if not p:
            return {"error": "No encontrado"}, 404
        its = c.execute("SELECT producto_id, cantidad, precio_unit FROM items WHERE pedido_id=?", (pid,)).fetchall()
    return {"pedido": dict(p), "items": [dict(x) for x in its]}

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT, debug=True)
