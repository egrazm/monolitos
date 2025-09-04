import os, sqlite3, logging, datetime
from functools import wraps
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

# Defaults simples (evitan NoneType si falta .env)
TOKEN   = os.getenv("SERVICE_TOKEN", "penguin-secret")
PORT    = int(os.getenv("PORT", "5004"))
DB_PATH = os.getenv("DB_PATH", "pagos.db")

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
            CREATE TABLE IF NOT EXISTS pagos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                monto REAL NOT NULL,
                moneda TEXT NOT NULL,
                medio TEXT NOT NULL,
                referencia TEXT,
                estado TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        con.commit()

@app.get("/health")
def health():
    return {"status": "ok", "service": "pagos"}

@app.post("/pagar")
@require_token
def pagar():
    data = request.get_json(silent=True) or {}
    monto = float(data.get("monto") or 0)
    moneda = data.get("moneda") or "PYG"
    medio = data.get("medio") or "tarjeta"
    referencia = data.get("referencia")
    fail = bool(data.get("fail", False))
    estado = "rechazado" if fail else "aprobado"

    with get_db() as con:
        c = con.cursor()
        c.execute(
            "INSERT INTO pagos (monto, moneda, medio, referencia, estado, created_at) VALUES (?,?,?,?,?,?)",
            (monto, moneda, medio, referencia, estado, datetime.datetime.utcnow().isoformat())
        )
        con.commit()
        pid = c.lastrowid

    return {"pago_id": pid, "estado": estado}

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT, debug=True)
