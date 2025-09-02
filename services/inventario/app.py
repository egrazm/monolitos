
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

def init_db():
    with get_db() as con:
        c = con.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS stock (
                producto_id INTEGER PRIMARY KEY,
                cantidad INTEGER NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS reservas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER NOT NULL,
                cantidad INTEGER NOT NULL,
                estado TEXT NOT NULL CHECK (estado IN ('activa','liberada','consumida')),
                created_at TEXT NOT NULL
            )
        """)
        con.commit()

@app.post("/stock")
@require_token
def upsert_stock():
    data = request.get_json(force=True)
    pid = data.get("producto_id")
    cantidad = data.get("cantidad")
    if not pid or cantidad is None:
        return {"error": "Faltan campos"}, 400
    with get_db() as con:
        c = con.cursor()
        row = c.execute("SELECT cantidad FROM stock WHERE producto_id=?", (pid,)).fetchone()
        if row:
            c.execute("UPDATE stock SET cantidad=? WHERE producto_id=?", (int(cantidad), pid))
        else:
            c.execute("INSERT INTO stock (producto_id, cantidad) VALUES (?,?)", (pid, int(cantidad)))
        con.commit()
    return {"ok": True}

@app.get("/stock/<int:pid>")
@require_token
def ver_stock(pid):
    with get_db() as con:
        c = con.cursor()
        row = c.execute("SELECT producto_id, cantidad FROM stock WHERE producto_id=?", (pid,)).fetchone()
    if not row:
        return {"producto_id": pid, "cantidad": 0}
    return dict(row)

@app.post("/reservar")
@require_token
def reservar():
    data = request.get_json(force=True)
    pid = data.get("producto_id")
    cantidad = int(data.get("cantidad") or 0)
    if not pid or cantidad <= 0:
        return {"error":"Faltan campos"}, 400
    with get_db() as con:
        c = con.cursor()
        row = c.execute("SELECT cantidad FROM stock WHERE producto_id=?", (pid,)).fetchone()
        actual = int(row["cantidad"]) if row else 0
        if actual < cantidad:
            return {"error":"Stock insuficiente", "disponible": actual}, 409
        nuevo = actual - cantidad
        c.execute("INSERT INTO reservas (producto_id, cantidad, estado, created_at) VALUES (?,?, 'activa', ?)", (pid, cantidad, datetime.datetime.utcnow().isoformat()))
        rid = c.lastrowid
        c.execute("REPLACE INTO stock (producto_id, cantidad) VALUES (?,?)", (pid, nuevo))
        con.commit()
    return {"reserva_id": rid, "producto_id": pid, "cantidad": cantidad}

@app.post("/liberar")
@require_token
def liberar():
    data = request.get_json(force=True)
    rid = data.get("reserva_id")
    if not rid: return {"error":"Falta reserva_id"}, 400
    with get_db() as con:
        c = con.cursor()
        res = c.execute("SELECT id, producto_id, cantidad, estado FROM reservas WHERE id=?", (rid,)).fetchone()
        if not res: return {"error":"Reserva no existe"}, 404
        if res["estado"] != "activa":
            return {"ok": True, "detalle": f"Reserva ya {res['estado']}"}
        # devolver stock
        row = c.execute("SELECT cantidad FROM stock WHERE producto_id=?", (res["producto_id"],)).fetchone()
        actual = int(row["cantidad"]) if row else 0
        nuevo = actual + int(res["cantidad"])
        c.execute("REPLACE INTO stock (producto_id, cantidad) VALUES (?,?)", (res["producto_id"], nuevo))
        c.execute("UPDATE reservas SET estado='liberada' WHERE id=?", (rid,))
        con.commit()
    return {"ok": True}

@app.post("/consumir")
@require_token
def consumir():
    data = request.get_json(force=True)
    rid = data.get("reserva_id")
    if not rid: return {"error":"Falta reserva_id"}, 400
    with get_db() as con:
        c = con.cursor()
        res = c.execute("SELECT id, estado FROM reservas WHERE id=?", (rid,)).fetchone()
        if not res: return {"error":"Reserva no existe"}, 404
        if res["estado"] != "activa":
            return {"ok": True, "detalle": f"Reserva ya {res['estado']}"}
        c.execute("UPDATE reservas SET estado='consumida' WHERE id=?", (rid,))
        con.commit()
    return {"ok": True}

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT, debug=True)
