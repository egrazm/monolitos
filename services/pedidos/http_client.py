import time
import logging
import requests
import os

log = logging.getLogger(__name__)

TOKEN = os.getenv("SERVICE_TOKEN")

# Estado de circuit breaker por servicio
CB = {}                # svc -> {failures:int, opened_until:float}
THRESHOLD = 3          # fallos consecutivos para abrir
OPEN_SECONDS = 30      # ventana en estado OPEN

def state_for(svc: str) -> dict:
    d = CB.get(svc)
    if d is None:
        d = {"failures": 0, "opened_until": 0.0}
        CB[svc] = d
    return d

def is_open(svc: str) -> bool:
    s = state_for(svc)
    return time.time() < s["opened_until"]

def open_circuit(svc: str) -> None:
    s = state_for(svc)
    s["opened_until"] = time.time() + OPEN_SECONDS
    log.warning("[CB] %s OPEN por %ss", svc, OPEN_SECONDS)

def record_success(svc: str) -> None:
    s = state_for(svc)
    s["failures"] = 0
    s["opened_until"] = 0.0

def record_failure(svc: str) -> None:
    s = state_for(svc)
    s["failures"] += 1
    if s["failures"] >= THRESHOLD:
        open_circuit(svc)

def request_json(method: str, url: str, svc: str, json=None, timeout: float = 5.0,
                 retries: int = 2, token: str | None = None):
    """
    Llamada HTTP con circuit breaker simple por servicio.
    - svc: nombre lógico del servicio destino ("productos", "inventario", "pagos"...)
    - retries: reintentos (además del intento inicial)
    - Si el circuito está OPEN, lanza RuntimeError
    Devuelve 'requests.Response'.
    """
    if token is None:
        token = TOKEN

    if is_open(svc):
        raise RuntimeError(f"Circuit breaker OPEN para {svc}")

    headers = {"Authorization": f"Bearer {token}"}
    if json is not None:
        headers["Content-Type"] = "application/json"

    last_err = None
    total_attempts = 1 + max(0, int(retries))
    for attempt in range(total_attempts):
        try:
            resp = requests.request(method, url, headers=headers, json=json, timeout=timeout)
            # Consideramos 5xx como fallo transitorio
            if resp.status_code >= 500:
                raise RuntimeError(f"HTTP {resp.status_code} desde {svc}")
            record_success(svc)
            return resp
        except Exception as e:
            last_err = e
            record_failure(svc)
            # backoff lineal muy simple: 0.5s, 1.0s, 1.5s...
            if attempt < total_attempts - 1:
                delay = 0.5 * (attempt + 1)
                log.warning("[retry] %s fallo: %s. Reintento en %.1fs", svc, e, delay)
                time.sleep(delay)
            else:
                break
    # Al salir sin éxito
    raise last_err
