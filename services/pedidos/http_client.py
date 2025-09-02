
import time, logging, requests, os

log = logging.getLogger(__name__)

TOKEN = os.getenv("SERVICE_TOKEN", "penguin-secret")
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# Circuit breaker muy simple por servicio
CB = {}
THRESHOLD = 3       # fallos para abrir
OPEN_SECONDS = 30   # ventana abierto

def _state(svc):
    d = CB.setdefault(svc, {"failures": 0, "opened_until": 0})
    return d

def _open(svc):
    st = _state(svc)
    st["opened_until"] = time.time() + OPEN_SECONDS
    log.warning(f"[CB] Servicio {svc} en estado OPEN por {OPEN_SECONDS}s")

def _is_open(svc):
    st = _state(svc)
    if time.time() < st["opened_until"]:
        return True
    return False

def _record_success(svc):
    st = _state(svc)
    st["failures"] = 0
    st["opened_until"] = 0

def _record_failure(svc):
    st = _state(svc)
    st["failures"] += 1
    if st["failures"] >= THRESHOLD:
        _open(svc)

def call_json(svc_name, method, url, json=None, timeout=3, retries=2):
    if _is_open(svc_name):
        raise RuntimeError(f"Circuit breaker OPEN para {svc_name}")
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = requests.request(method, url, headers=HEADERS, json=json, timeout=timeout)
            if resp.status_code >= 500:
                raise RuntimeError(f"HTTP {resp.status_code} desde {svc_name}")
            _record_success(svc_name)
            return resp
        except Exception as e:
            last_err = e
            _record_failure(svc_name)
            if attempt < retries:
                backoff = 0.5 * (attempt + 1)
                log.warning(f"[retry] {svc_name} fallo: {e}. Reintentando en {backoff}s...")
                time.sleep(backoff)
            else:
                break
    raise last_err
