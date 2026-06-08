# RDOC04 – Documentación Pipeline CI/CD

## Objetivo

El pipeline CI/CD automatiza la construcción y publicación de nuevas versiones del backend de CityExpress. Cada vez que se realiza un push a la rama principal del repositorio, GitHub Actions construye una nueva imagen Docker de la aplicación y la publica automáticamente en Amazon Elastic Container Registry (ECR).

Esta automatización elimina la necesidad de construir y publicar imágenes manualmente, asegurando que todas las versiones desplegadas sean consistentes y reproducibles.

## Flujo General

```text
Developer
    │
    │ git push
    │
    ▼
GitHub Repository
    │
    ▼
GitHub Actions
    │
    ├── Checkout código
    ├── Configurar AWS
    ├── Login ECR
    ├── Build Docker Image
    ├── Tag Docker Image
    ├── Push Docker Image
    ├── Crear Deployment
    └── Ejecutar CodeDeploy
    │
    ▼
Amazon ECR
    │
    ▼
AWS CodeDeploy
    │
    ▼
EC2 Producción
    │
    ├── Descargar artefacto
    ├── Ejecutar deploy.sh
    ├── Docker Pull
    ├── Docker Compose Down
    └── Docker Compose Up
    │
    ▼
Nueva versión desplegada
```

## Trigger del Pipeline

El pipeline se ejecuta automáticamente cuando se realiza un push sobre la rama configurada en el workflow.

```yaml
on:
  push:
    branches:
      - main
      - develope
```

De esta forma, cada modificación integrada a la rama principal o desarrollo genera una nueva versión de la imagen Docker. Esta implementación se realizo de esta manera para facilitar el testeo.

## Etapas del Pipeline

### 1. Checkout del Repositorio

```yaml
- name: Checkout
  uses: actions/checkout@v4
```

Descarga el contenido del repositorio dentro del runner de GitHub Actions para que los pasos posteriores puedan acceder al código fuente. El código del backend queda disponible en el entorno de ejecución.

### 2. Configuración de Credenciales AWS

```yaml
- name: Configure AWS
  uses: aws-actions/configure-aws-credentials@v4
  with:
    aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
    aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    aws-region: ${{ secrets.AWS_REGION }}
```

Configura credenciales temporales de AWS utilizando los secretos almacenados en GitHub, permitiendo interactuar con los servicios AWS necesarios para el despliegue.

### 3. Login en Amazon ECR

```yaml
- name: Login ECR
  uses: aws-actions/amazon-ecr-login@v2
```

Autentica Docker contra Amazon Elastic Container Registry, permitiendo que Docker pueda publicar imágenes dentro del repositorio ECR.

### 4. Construcción de la Imagen Docker

```yaml
- name: Build Image
  run: |
    docker build -t $ECR_REPOSITORY .
```

Construir una nueva imagen Docker utilizando el Dockerfile del proyecto, permite que se genere una imagen local con todo el backend empaquetado y listo para ejecutarse.

### 5. Etiquetado de la Imagen

```yaml
- name: Tag Image
  run: |
    docker tag $ECR_REPOSITORY:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest
```

Asignar a la imagen construida el identificador requerido por Amazon ECR, permitiendo que la imagen queda asociada al repositorio ``cityexpress-api:latest`` dentro de la cuenta AWS correspondiente.

### 6. Publicación de la Imagen

```yaml
- name: Push Image
  run: |
    docker push \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest
```

Enviar la imagen Docker generada hacia Amazon ECR, permitiendo que la nueva versión del backend queda almacenada en ``Amazon Elastic Container Registry (ECR)`` y disponible para ser utilizada por los servidores de producción.

### 7. Creación del Deployment en CodeDeploy

```yaml
- name: Deploy
  run: |
    aws deploy create-deployment \
      --application-name CityExpressBackend \
      --deployment-group-name cityexpress-backend-group \
      --github-location repository=$GITHUB_REPOSITORY,commitId=$GITHUB_SHA
```

Solicitar a AWS CodeDeploy la ejecución de un nuevo despliegue utilizando la versión recién publicada del repositorio.
CodeDeploy crea una nueva ejecución asociada al commit que generó el pipeline.

### 8. Ejecución del Despliegue en EC2

Una vez recibido el deployment, CodeDeploy utiliza los archivos definidos en el repositorio:

#### appspec.yml

Define qué archivos copiar al servidor y qué scripts ejecutar durante el proceso de despliegue.

Ejemplo:

```yaml
version: 0.0
os: linux

files:
  - source: /
    destination: /home/ubuntu

hooks:
  ApplicationStart:
    - location: deploy.sh
      timeout: 300
      runas: ubuntu
```

#### deploy.sh

Script ejecutado por CodeDeploy dentro de la instancia EC2.

```bash
#!/bin/bash
set -e

cd /home/ubuntu

aws ecr get-login-password --region us-east-2 \
  | docker login --username AWS --password-stdin 127621463290.dkr.ecr.us-east-2.amazonaws.com

docker pull 127621463290.dkr.ecr.us-east-2.amazonaws.com/cityexpress-api:latest

docker compose -f docker-compose.prod.yml down

docker compose -f docker-compose.prod.yml up -d
```

Actualizar automáticamente la instancia EC2 con la última imagen disponible en ECR. La nueva versión queda ejecutándose sin necesidad de intervención manual.

## Infraestructura AWS Utilizada

### Amazon ECR

Repositorio privado utilizado para almacenar las imágenes Docker del backend.

Contiene la imagen:

```text
cityexpress-api:latest
```

### AWS CodeDeploy

Servicio encargado de orquestar el despliegue automático sobre las instancias EC2.

Responsabilidades:

- Descargar la nueva revisión.
- Copiar archivos definidos en appspec.yml.
- Ejecutar scripts de despliegue.
- Reportar estado del deployment.

### Amazon EC2

Servidor de producción donde se ejecuta la aplicación.

La instancia:

- Posee Docker instalado.
- Posee Docker Compose instalado.
- Tiene asociado un IAM Role con permisos para:
  - Amazon ECR
  - AWS CodeDeploy

## Variables y Secretos Utilizados

### GitHub Secrets

| Variable | Descripción |
|--|-|
| AWS_ACCESS_KEY_ID | Credencial de acceso AWS |
| AWS_SECRET_ACCESS_KEY | Clave secreta AWS |
| AWS_ACCOUNT_ID | Identificador de la cuenta AWS |
| AWS_REGION | Región AWS utilizada |
| ECR_REPOSITORY | Nombre del repositorio ECR |

## Beneficios Obtenidos

La implementación del pipeline permite:

- Automatizar la construcción de imágenes Docker.
- Reducir errores humanos durante el despliegue.
- Mantener una única versión oficial de la aplicación.
- Garantizar reproducibilidad entre entornos.
- Facilitar futuras extensiones hacia despliegues completamente automáticos mediante AWS CodeDeploy.

## Tecnologías Utilizadas

- GitHub Actions
- Docker
- Docker Compose
- Amazon Elastic Container Registry (ECR)
- AWS CodeDeploy
- Amazon EC2
- AWS IAM