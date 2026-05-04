# Prompts - RichardUC

## Flujo de conversación con Gemini - Backend CityExpress

### Resumen general
Se utilizó Gemini como asistente experto para el desarrollo del backend de CityExpress.

---

## Errores resueltos

## 1. URL para probar la instancia EC2 directamente
**Prompt:** ¿Qué URL uso para probar mi EC2?  
**Respuesta:** Usa el DNS público o la IP pública con puerto 8000. ``Ejemplo: http://13.59.84.29:8000/health``. Asegura la regla Inbound para el puerto 8000 en el Security Group.

### 2. Pruebas de filtros en la ruta GET /packages/
**Prompt:** ¿Cómo pruebo la ruta en GET /packages/?  
**Respuesta:** Validar la funcionalidad mediante peticiones cURL o el navegador utilizando Query Parameters. Para la lista total se usa la URL base del Gateway; para los filtros del RF01, se concatenan los parámetros tras un signo de interrogación (ej. ?status=entregado&origin_id=5). Es crucial que en FastAPI la función reciba los argumentos como opcionales (status: str = None) y que el API Gateway tenga configurada la ruta o el proxy correspondiente para redirigir el tráfico a la EC2.

### 3. Error OperationalError: could not translate host name "db"
**Prompt:** "psycopg2.OperationalError: could not translate host name 'db' to address: Temporary failure in name resolution"
**Respuesta:** Verifica que la cadena de conexión use exactamente el servicio `db` (postgresql://user:pass@db:5432/db) y reinicia `api` después de que `db` esté en estado healthy.

### 4. Error de puerto ocupado (PostgreSQL) al levantar Docker Compose
**Prompt:** failed to bind host port 0.0.0.0:5432/tcp  
**Respuesta:** Detén el Postgres local (`sudo service postgresql stop`) o cambia el mapeo de puertos en producción.

### 5. La imagen en la EC2 no se actualiza tras un docker pull
**Prompt:** "Ahora mismo tengo un problema, estoy subiendo toda la informacion al ECR... al momento de copiar la nueva imagen no se actualiza [...] ``sudo docker build -t cityexpress-api`` . falla con no such file or directory"
**Respuesta:** Realizar un docker pull no actualiza automáticamente los contenedores en ejecución. Se debe seguir un flujo de actualización "limpio": 1. Detener y eliminar contenedores antiguos (docker stop y docker rm) para liberar el puerto 8000. 2. Descargar la imagen fresca del ECR. 3. Ejecutar un nuevo contenedor con docker run. El error de build en la EC2 ocurre porque el servidor no contiene el Dockerfile (el código fuente); el build debe realizarse localmente antes del push.

### 6. Configuración de permisos IAM para API Gateway
**Prompt:** "Con que permiso le doy acceso al API Gateway [imagen]"
**Respuesta:** Según necesidad: `AmazonAPIGatewayInvokeFullAccess` (invocación) o `AmazonAPIGatewayAdministrator` (gestión). El acceso a la EC2 se controla con Security Groups.

### 7. Configuración de Integración y Parámetros en API Gateway
**Prompt:** ¿La integración de /{package_id} está bien? [Imagen de la configuración realizada en API Gateway]  
**Respuesta:** Usa la Integration URI con la variable en la ruta (ej. http://ec2-ip:8000/packages/{package_id}) o un recurso `ANY /{proxy+}` para simplificar y evitar mapeos manuales.

### 8. Error de validación "Invalid Request Actioned Parameter" en API Gateway
**Prompt:** Error por parámetro invalidado en API Gateway  
**Respuesta:** Evita mappings manuales; define la variable en la Integration URI (ej. http://ec2-ip:8000/packages/{package_id}) y que el nombre coincida con la ruta.


### 9. Visualización de métricas en New Relic
**Prompt:** ¿Dónde veo las métricas de la aplicación?  
**Respuesta:** Revisa APM & Services para transacciones HTTP y Infrastructure para métricas de host (CPU, memoria, disco). Genera tráfico manual; datos tardan minutos en aparecer.

### 10. Identificación del paquete más reciente en logs
**Prompt:** "Analiza la lista de paquetes que te compartarto y dime el dato más reciente (basado en la fecha de creación created_at) es el siguiente..." (Referencia a la lista de paquetes proporcionada previamente).
**Respuesta:** Se identificó el paquete con ID 274eb682... creado el 2026-05-02 a las 07:08:53 como el registro más actual del conjunto de datos.
Contexto: Buscaba identificar que estaba funcionando en consumidor localmente para mas adelante realizar la copia en el ECR, identificando su habian paquetes recientes.

### 11. Advertencia de Tini (child subreaper) en New Relic
**Prompt:** "que dice esto de aca: newrelic-infra | To fix the problem, use the -s option or set the environment variable TINI_SUBREAPER..."
**Respuesta:** Al usar `pid: host` Tini ya no es PID 1; añade `TINI_SUBREAPER=1` en el contenedor o ignora si el agente se conecta correctamente.

