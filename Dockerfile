# Imagen de Python (version ligera por el free trier de AWS)
FROM python:3.10-slim

# Directorio de trabajo en el contenedor
WORKDIR /app

# Copiar requerimientos para el cache de Docker
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar resto del codigo en src
COPY ./src ./src

# Exponer el puerto
EXPOSE 8000

# Comando para iniciar el servidor en desarrollo
# 2 worker para evitar que se congele la cola
# arreglo para q tablas se crean antes de arrancar uvicorn, y en tests no toca postgre
CMD ["sh", "-c", "python3 -c 'from src.database import engine, Base; from src.models import Package, CityConnection, PackageEvent; Base.metadata.create_all(bind=engine)' && uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 2"]
