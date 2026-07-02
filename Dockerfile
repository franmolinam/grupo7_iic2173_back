# Imagen de Python (version ligera por el free trier de AWS)
FROM python:3.10-slim

# Directorio de trabajo en el contenedor
WORKDIR /app

# Copiar requerimientos para el cache de Docker
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar la configuracion de new relic
COPY newrelic.ini /app/newrelic.ini

# Copiar resto del codigo en src
COPY ./src ./src

# Exponer el puerto
EXPOSE 8000

# Comando para iniciar el servidor en desarrollo
# 1 worker: el feed SSE (src/sse.py) guarda los suscriptores en memoria del proceso,
# con >1 worker los eventos emitidos por el consumer o por otro worker se pierden si
# el cliente SSE quedó conectado a un proceso distinto.
# arreglo para q tablas se crean antes de arrancar uvicorn, y en tests no toca postgre
CMD ["sh", "-c", "python3 -c 'from src.database import engine, Base; from src.models import Package, CityConnection, PackageEvent, ShipmentRequest, Payment, RoutingJob, Subscription, SubscriptionPackage; Base.metadata.create_all(bind=engine)' && newrelic-admin run-program uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1"]