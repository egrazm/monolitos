# 🐧 Microservicios Pingüinos — Demo mínima (Flask + SQLite + Token)


## 🧩 Servicios incluidos

- **productos** (puerto 5001): CRUD de productos (nombre, precio).
- **inventario** (puerto 5002): stock + reservas (reservar/liberar).
- **pagos** (puerto 5003): simula cobro (éxito o fallo controlado).
- **pedidos** (puerto 5004): crea pedidos hablando con los demás (usa **retry + circuit breaker**).

Cada servicio:
- expone **endpoints REST**,
- valida `Authorization: Bearer <SERVICE_TOKEN>`,
- usa **SQLite** propio (archivos `.db` distintos),
- tiene logs a consola y a `logs.log`.

---

## 🚀 Puesta en marcha
> Requisitos: Python 3.10+

En **cuatro terminales** (una por servicio), dentro de cada carpeta `/services/<nombre>`:

```bash
# 1) Crear venv y activar (Linux/Mac)
python -m venv venv
source venv/bin/activate

# En Windows PowerShell
# python -m venv venv
# .\venv\Scripts\Activate.ps1

# 2) Instalar dependencias
pip install -r requirements.txt

# 3) Copiar .env.example a .env
cp .env.example .env
# (en Windows PowerShell: copy .env.example .env)

# 4) Ejecutar
python app.py
```

### Variables de entorno
Todos comparten `SERVICE_TOKEN` (mismo valor en los 4). **Por defecto:** `penguin-secret`.

- `productos/.env.example`
  ```ini
  PORT=5001
  SERVICE_TOKEN=penguin-secret
  DB_PATH=productos.db
  ```

- `inventario/.env.example`
  ```ini
  PORT=5002
  SERVICE_TOKEN=penguin-secret
  DB_PATH=inventario.db
  ```

- `pagos/.env.example`
  ```ini
  PORT=5003
  SERVICE_TOKEN=penguin-secret
  DB_PATH=pagos.db
  ```

- `pedidos/.env.example`
  ```ini
  PORT=5004
  SERVICE_TOKEN=penguin-secret
  PRODUCTS_URL=http://127.0.0.1:5001
  INVENTORY_URL=http://127.0.0.1:5002
  PAYMENTS_URL=http://127.0.0.1:5003
  DB_PATH=pedidos.db
  ```

---

## 🧪 Pruebas rápidas (cURL)
> Asegurate de que los 4 servicios estén corriendo.

### 1) Crear un producto
```bash
curl -X POST http://127.0.0.1:5001/productos   -H "Authorization: Bearer penguin-secret" -H "Content-Type: application/json"   -d '{"nombre": "Hielo Premium", "precio": 10000}'
```

### 2) Cargar stock
```bash
curl -X POST http://127.0.0.1:5002/stock   -H "Authorization: Bearer penguin-secret" -H "Content-Type: application/json"   -d '{"producto_id": 1, "cantidad": 50}'
```

### 3) Crear pedido (flujo feliz)
```bash
curl -X POST http://127.0.0.1:5004/pedidos   -H "Authorization: Bearer penguin-secret" -H "Content-Type: application/json"   -d '{"items":[{"producto_id":1,"cantidad":3}], "pago":{"medio":"tarjeta","moneda":"PYG"}}'
```

### 4) Simular fallo de pago (libera reservas automáticamente)
```bash
curl -X POST http://127.0.0.1:5004/pedidos   -H "Authorization: Bearer penguin-secret" -H "Content-Type: application/json"   -d '{"items":[{"producto_id":1,"cantidad":2}], "pago":{"medio":"tarjeta","moneda":"PYG","fail":true}}'
```

---

## 🔌 Endpoints clave (extracto)

### productos (5001)
- `POST /productos` — crea (body: `{"nombre","precio"}`)
- `GET /productos` — lista
- `GET /productos/<id>` — detalle
- `PUT /productos/<id>` — edita
- `DELETE /productos/<id>` — borra

### inventario (5002)
- `POST /stock` — upsert de stock `{producto_id, cantidad}`
- `GET /stock/<producto_id>` — consulta
- `POST /reservar` — reserva `{producto_id, cantidad}` → `{reserva_id}`
- `POST /liberar` — libera `{reserva_id}`

### pagos (5003)
- `POST /pagar` — `{monto, moneda, medio, referencia?, fail?}` → `{estado: aprobado|rechazado}`

### pedidos (5004)
- `POST /pedidos` — crea pedido, orquestando a **inventario**, **productos**, **pagos**
- `GET /pedidos` — lista
- `GET /pedidos/<id>` — detalle

---

## 🛡️ Seguridad
- **Header** obligatorio: `Authorization: Bearer <SERVICE_TOKEN>`
- Si no coincide, **401 Unauthorized**.

---

## 🧯 Resiliencia (en `pedidos`)
- **Reintentos** con *backoff* simple (2 intentos).
- **Circuit breaker** por servicio llamado (se abre a los 3 fallos y se cierra tras 30s).

> Fácil de ver en `services/pedidos/http_client.py`.

---

## 🗃️ Bases de datos
Cada servicio crea sus propias tablas SQLite en su carpeta. **No se comparten**.

---

## 📝 Logs
Cada servicio escribe a consola y a un archivo `logs.log` en su carpeta.

---

## 🧠 ¿Por qué así de simple?
- **Tokens compartidos** en headers (sin infraestructura OAuth).
- **SQLite** por servicio (cero Docker obligatorio).
- **Flask** mínimo + `requests` para hablar por HTTP.
- *Circuit breaker* 👇 y *retry* suficientes para el challenge.

¡Listo! Copiá este proyecto, ajustá a tu gusto y… 🎉 **chau Mamut**.
