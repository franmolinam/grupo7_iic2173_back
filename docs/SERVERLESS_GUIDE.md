# RDOC03: Documentación de Serverless (servicio de ruteo)

## 1. Prerrequisitos

- **Node.js y npm**: necesarios para instalar y gestionar el framework Serverless y sus plugins.
- **Instalar Serverless Framework CLI**: comando `npm install -g serverless`.
- **Credenciales AWS**:  se deben ingresar credenciales válidas con los permisos para crear funciones Lambda y configurar API Gateway.
- **Python 3.10+**: instalado localmente para el funcionamiento del plugin `serverless-python-requirements`.

## 2. Instalación de Plugins
Para que el framework pueda compilar e inyectar automáticamente las librerías de `requirements.txt` y leer las variables de entorno, se deben utilizar plugins.

Desde la terminal, posicionarse en la carptea jobs_master y ejecutar `npm install serverless-python-requirements serverless-dotenv-plugin`

## 3. Deploy en AWS
Ejecutar el comando `serverless deploy`. Lo que hace esto es empaquetar el código fuente de Python, subir el paquete a un bucket de S3 temporal, crear y configurar la función de AWS Lambda, configurar los endpoints mediante Amazon API Gateway y asignar los roles de IAM para la ejecución del servicio.

## 4. Enlace con EC2
Una vez que el comando anterior corra sin errores, se espera un resultado de este estilo:
``` bash
POST - https://[id-api].execute-api.[region].amazonaws.com/job
GET - https://[id-api].execute-api.[region].amazonaws.com/job/{jobId}
```
Esta URL debe ser escrita en el archivo .env de la instancia para que los workers funcionen de forma exitosa. En el presente proyecto, el nombre de la variable es JOBS_MASTER_URL.