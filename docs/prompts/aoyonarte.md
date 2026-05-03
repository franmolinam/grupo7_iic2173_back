# Prompts - Aoyonarte

## Flujo de conversación con Claude - Backend CityExpress

### Resumen general
Se utilizó Claude como asistente para el desarrollo del backend de CityExpress.

---

## Errores resueltos

### 1. Error de conexión DB al arrancar la API antes que Postgres
**Prompt:** "La API arranca antes que la DB esté lista y tira error de conexión"
**Respuesta:** Agregar healthcheck a Postgres en docker-compose.yml con `pg_isready`
y usar `depends_on: condition: service_healthy` en el servicio api.

### 2. Error declarative_base deprecado en SQLAlchemy 2.0
**Prompt:** "Sale warning MovedIn20Warning en declarative_base"
**Respuesta:** Cambiar `from sqlalchemy.ext.declarative import declarative_base`
por `from sqlalchemy.orm import declarative_base`.

### 3. Tests de handlers fallaban por falta de CityConnection en DB
**Prompt:** "3 tests de handlers fallan con 'expire' en vez de 'forward'"
**Respuesta:** Los tests no sembraban conexiones en la DB. Agrega un helper
`seed_connection(db)` para crear una CityConnection habilitada antes de cada test
que requiere ruteo.

### 4. MagicMock no tiene __name__ en fibonacci_retry
**Prompt:** "test_fibonacci_retry_raises_after_max_retries falla con AttributeError: __name__"
**Respuesta:** Agregar `mock_func.__name__ = "mock_func"` al MagicMock antes
de decorarlo con fibonacci_retry.

### 5. Error de Nginx: server_names_hash_bucket_size
**Prompt:** "nginx -t falla con 'could not build server_names_hash, you should
increase server_names_hash_bucket_size: 64'"
**Respuesta:** Agregar `server_names_hash_bucket_size 128;` dentro del bloque
`http {}` en `/etc/nginx/nginx.conf`.

### 6. Nginx devuelve 404 en vez de hacer proxy a la API
**Prompt:** "curl http://localhost/health devuelve 404 Not Found de Nginx"
**Respuesta:** El sitio `default` de Nginx estaba interfiriendo. Se eliminó con
`sudo rm /etc/nginx/sites-enabled/default` y se reinició Nginx.

### 7. ModuleNotFoundError: No module named 'jose'
**Prompt:** "ERROR collecting tests/test_routes.py — No module named 'jose'"
**Respuesta:** Instalar localmente con `pip install python-jose`.

### 8. ModuleNotFoundError: No module named 'pika'
**Prompt:** "ERROR collecting tests/test_rabbitmq.py — No module named 'pika'"
**Respuesta:** Instalar localmente con `pip install pika`.