
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
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                precio REAL NOT NULL
            )
        """)
        con.commit()

@app.post("/productos")
@require_token
def crear_producto():
    data = request.get_json(force=True)
    nombre = data.get("nombre")
    precio = data.get("precio")
    if not nombre or precio is None:
        return {"error": "Faltan campos"}, 400
    with get_db() as con:
        c = con.cursor()
        c.execute("INSERT INTO productos (nombre, precio) VALUES (?,?)", (nombre, float(precio)))
        con.commit()
        pid = c.lastrowid
    return {"id": pid, "nombre": nombre, "precio": float(precio)}, 201

@app.get("/productos")
@require_token
def listar_productos():
    with get_db() as con:
        c = con.cursor()
        rows = c.execute("SELECT id, nombre, precio FROM productos").fetchall()
    return {"items": [dict(r) for r in rows]}

@app.get("/productos/<int:pid>")
@require_token
def detalle_producto(pid):
    with get_db() as con:
        c = con.cursor()
        row = c.execute("SELECT id, nombre, precio FROM productos WHERE id=?", (pid,)).fetchone()
    if not row:
        return {"error": "No encontrado"}, 404
    return dict(row)

@app.put("/productos/<int:pid>")
@require_token
def editar_producto(pid):
    data = request.get_json(force=True)
    nombre = data.get("nombre")
    precio = data.get("precio")
    if nombre is None and precio is None:
        return {"error": "Nada para actualizar"}, 400
    with get_db() as con:
        c = con.cursor()
        row = c.execute("SELECT id FROM productos WHERE id=?", (pid,)).fetchone()
        if not row: return {"error":"No encontrado"}, 404
        if nombre is not None:
            c.execute("UPDATE productos SET nombre=? WHERE id=?", (nombre, pid))
        if precio is not None:
            c.execute("UPDATE productos SET precio=? WHERE id=?", (float(precio), pid))
        con.commit()
    return {"ok": True}

@app.delete("/productos/<int:pid>")
@require_token
def borrar_producto(pid):
    with get_db() as con:
        c = con.cursor()
        c.execute("DELETE FROM productos WHERE id=?", (pid,))
        con.commit()
    return {"ok": True}

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT, debug=True)
