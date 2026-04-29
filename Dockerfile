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
# 4 worker para evitar que se congele la cola
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]