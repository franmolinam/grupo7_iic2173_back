# RDOC03: Guía de Instalación y Testeo Local

## Descripción General
Guía práctica para configurar el entorno local de CityExpress, levantar la API con Docker, validar su funcionamiento mediante endpoints y tests, y resolver problemas comunes de ejecución en desarrollo.

## 1. Requisitos
Los requisitos generales estarán basados en el uso en Ubuntu y en el entorno de desarrollo. Por lo que se deberán ejecutar los siguientes comandos para instalar los paquetes; además, se considerará que ya tendrán clonado el repositorio de GitHub.

### 1.1 Instalación de Python y Paquetes
Realiza una instalación de Python y los paquetes utilizados para la instalación de sus librerías.

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

### 1.2 Instalación de Docker Engine
Ejecute el siguiente comando para desinstalar todos los paquetes conflictivos:

```bash
sudo apt remove $(dpkg --get-selections docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc | cut -f1)
```

`apt` es posible que indique que no tiene ninguno de estos paquetes instalados.

Antes de instalar Docker Engine por primera vez en una nueva máquina host, debe configurar el `apt` repositorio de Docker. Posteriormente, podrá instalar y actualizar Docker desde dicho repositorio.

1. Configura `apt` al repositorio de Docker.

    ```bash
    # Add Docker's official GPG key:
    sudo apt update
    sudo apt install ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    # Add the repository to Apt sources:
    sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
    Types: deb
    URIs: https://download.docker.com/linux/ubuntu
    Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
    Components: stable
    Architectures: $(dpkg --print-architecture)
    Signed-By: /etc/apt/keyrings/docker.asc
    EOF

    sudo apt update
    ```

2. Instala los paquetes de Docker.

    ```bash
    sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    ```

    > [!NOTE]
    >
    > Tras la instalación, verifique que Docker se esté ejecutando:
    >
    > ```bash
    > sudo systemctl status docker
    > ```
    >
    > Si Docker no se está ejecutando, inícielo manualmente:
    >
    > ```bash
    > sudo systemctl start docker
    > ```

3. Verifique que la instalación se haya realizado correctamente ejecutando la imagen `hello-world`:

    ```bash
    sudo docker run hello-world
    ```

    Este comando descarga una imagen de prueba y la ejecuta en un contenedor. Cuando el contenedor se ejecuta, imprime un mensaje de confirmación y finaliza.

### 1.3 Entorno Virtual
En la raíz del proyecto, ejecuta los siguientes comandos si no tienes creado un entorno virtual.

1. Crea un entorno virtual `.venv`

    ```bash
    python3 -m venv .venv
    ```

2. Activa el entorno virtual

    ```bash
    source .venv/bin/activate
    ```

### 1.4 Librerías del Proyecto (Desarrollo)
Ejecuta los comandos para instalar las dependencias desde `requirements.txt`

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 1.5 Librerías del Proyecto (Testing)
Ejecuta los comandos para instalar las dependencias para testear el proyecto.

```bash
pip install --upgrade pip
pip install anyio[trio] pytest-anyio
pip install pytest pytest-cov
```

### 1.6 Archivo .env
Para ejecutar la aplicación localmente, es necesario crear un archivo `.env` en la raíz del repositorio, con las siguientes variables:

```python
POSTGRES_USER=YOUR_DB_USER
POSTGRES_PASSWORD=YOUR_DB_PASSWORD
POSTGRES_DB=YOUR_DB_NAME

DATABASE_URL=postgresql://YOUR_DB_USER:YOUR_DB_PASSWORD@db:5432/YOUR_DB_NAME

# Datos para la conexion al broker
RABBITMQ_HOST=YOUR_RABBITMQ_HOST
RABBITMQ_PORT=YOUR_RABBITMQ_PORT
RABBITMQ_USER=YOUR_RABBITMQ_USER
RABBITMQ_PASSWORD=YOUR_RABBITMQ_PASSWORD
CODIGO_CIUDAD=YOUR_CITY_CODE

# Datos del AWS para la conexion del EC2 con el ECR
API_IMAGE_URI=YOUR_API_IMAGE_URI

# Datos de variables para Auth0 y JWK
AUTH0_DOMAIN=YOUR_AUTH0_DOMAIN
AUTH0_AUDIENCE=YOUR_AUTH0_AUDIENCE

# Datos de licencia de New Relic
NEW_RELIC_LICENSE_KEY=YOUR_NEW_RELIC_LICENSE_KEY
```

## 2. Testeo de la Aplicación
Para validar el funcionamiento de la aplicación, ejecuta los siguientes comandos desde la raíz del proyecto una vez completada la instalación de requisitos:

### 2.1 Contrucción de Contenedores

Para crear y ejecutar los contenedores en modo desarrollo, asegúrate de que Docker esté corriendo y luego ejecuta los siguientes comandos desde la raíz del proyecto:

```bash
sudo docker compose build
sudo docker compose up -d
sudo docker compose ps 
```
El último comando le servirá para comprobar que los contenedores fueron creados y están funcionando, observándose a través del mensaje `UP`.

### 2.2 Endpoints

Puedes ejecutar los siguientes comandos para probar los endpoints del programa:

```bash 
# Root: Ruta de bienvenida.
curl -i -X GET http://localhost:8000/

# Health: Ruta que verifica que el servicio y que la base de datos estén operando.
curl -i -X GET http://localhost:8000/health

# Listado de Paquetes: Obtiene todos los paquetes recibidos por la ciudad.
curl -i -X GET http://localhost:8000/packages

# Detalle de un Paquete: Ruta que obtiene el detalle de un paquete.
# Reemplaza el {package_id} por un id existente entregado en la ruta anterior.
curl -i -X GET http://localhost:8000/packages/{package_id}

# Estado de Conexiones: Ruta que muestra la tabla de distancias y conectividad con otras ciudades.
curl -i -X GET http://localhost:8000/connections

# Entrega de Paquete: Ruta que concreta la entrega de un paquete si cumple con la fecha deliverNotBefore.
# Reemplaza el {package_id} por un id existente entregado en la ruta anterior.
curl -i -X POST http://localhost:8000/packages/{package_id}/deliver

# Si se pone un paquete que su status=pending_delivery y su deliver_not_before ya pasó, al hacer el curl retorna un mensaje de que fue entregado exitosamente y el paquete con status: delivered. Si luego se vuelve a realizar el mismo endpoint, para el mismo paquete, este retorna status: 400 y dice que el paquete ya fue enviado ("Package already delivered").

# Acceso Privado: Ruta que requiere un Bearer Token configurado mediante Auth0.
curl -i -X GET https://api.quackpackagemo.me/api/private \
  -H "Authorization: Bearer eyJ..." 
  -H "Content-Type: application/json"
```

### 2.3 Consumidor

Ejecuta manualmente el worker de RabbitMQ para conectarse con el broker.

```bash
sudo docker compose exec api python -m src.rabbitmq.consumer
```
Se espera que aparezcan varios paquetes al cargar el consumidor.

### 2.4 Test

Ejecuta pruebas unitarias y mide la cobertura de los tests.

```bash
python3 -m pytest tests/ --cov=src --cov-report=term-missing
```

## 3. Consideraciones
En algunos casos, al trabajar localmente con Docker, los servicios pueden no iniciar correctamente y generar problemas de conexión con la base de datos del contenedor tras la construcción. Si detectas conflictos de puertos, puedes ejecutar los siguientes comandos para liberar el puerto y reiniciar el entorno.

```bash
sudo service postgresql stop
# O si usas systemd:
sudo systemctl stop postgresql
```
y despues vuelves a ejecutar:

```bash
sudo docker compose up -d
```

Otra alternativa útil es reiniciar Docker y reconstruir los contenedores para asegurar un arranque limpio.

```bash
sudo docker compose down
sudo docker compose build
sudo docker compose up -d
```

Si aun así el puerto no se libera y no parece ser un problema de Docker ni de postgres, puedes inspeccionarlo con el siguiente comando:

```bash
sudo lsof -i :5432
```