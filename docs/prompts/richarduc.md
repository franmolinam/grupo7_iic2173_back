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

### 12. Estrategia de control de acceso y separación de roles con Auth0 (RNF05)
**Prompt:** "Estoy diseñando la separación de roles (admin/usuario) usando los tokens de Auth0. ¿Qué estrategia me recomiendas para implementarlo en FastAPI?"
**Respuesta:** Se recomendó una verificación en la capa de aplicación usando el campo `sub` del JWT y una lista en variables de entorno (`ADMIN_USERS`). Creando la función `is_admin()` y la dependencia de FastAPI `require_admin()` para restringir el acceso.

### 13. Diseño de la API administrativa (RF08)
**Prompt:** "Para el módulo administrativo del RF08, planifiqué exponer las entidades clave del sistema. ¿Esta estructura de endpoints que ideé es la óptima y más limpia según nuestro modelo de datos?"
**Respuesta:** Se analizaron y validaron los endpoints independientes bajo un router de administración para auditar las cuatro entidades clave del sistema: `/jobs` (ruteo), `/routes` (rutas), `/packages` (paquetes) y `/payments` (pagos).

### 14. Optimización de persistencia para rutas calculadas (RF08)
**Prompt:** "Quiero optimizar el almacenamiento del panel administrador. ¿Es estrictamente necesario que cree una nueva tabla para el histórico de rutas o puedo reutilizar de alguna forma los modelos que ya tengo?"
**Respuesta:** No es necesario. Se recomendó configurar el backend para reutilizar los campos nativos de trazabilidad (`full_path`, `next_hop`, `hops_count`, `route_metric_cost`) ya existentes en la tabla `ShipmentRequest`, evitando redundancia de datos.

### 15. Validación de aislamiento de datos en envíos (RF05)
**Prompt:** "Revisemos mi lógica en el endpoint `/shipments/my-shipments`. ¿Cómo puedo asegurar rigurosamente que mi query actual cumpla con el aislamiento estricto de datos por usuario del RF05?"
**Respuesta:** Se validó que el query del ORM extrae el `sub` directamente del token autenticado y aplica un filtro forzado (`filter_by(user_id=user_id)`), impidiendo que un usuario acceda a datos de otros.

### 16. Optimización y corrección del pipeline de CI/CD (RNF08)
**Prompt:** "Creé un workflow en GitHub Actions. Quiero que revises los posible errores en el archivo YAML y ayudarme a corregirlos para que funcione correctamente."
**Respuesta:** Se analizaron los logs de error del pipeline, corrigiendo los fallos en las etapas de autenticación y empaquetado. Se reestructuró el workflow para que, ante cada `push` en `main`, automatice de forma segura la autenticación en AWS, el login en ECR, y la construcción, etiquetado y subida sin errores de la nueva imagen Docker del backend.

### 17. Configuración de secretos y variables en GitHub Actions
**Prompt:** "Ya tengo estructurado el workflow de CI/CD, pero no quiero dejar expuestas mis credenciales de AWS en el código. ¿Como configuro las variables en github action? [imagen]" 
**Respuesta:** Se guio en el proceso de configuración de *Repository Secrets* desde la interfaz de GitHub. Se recomendó centralizar estos valores mediante un bloque de entorno global (`env`) en la raíz del archivo YAML, invocando de forma segura secretos como `AWS_REGION`, `AWS_ACCOUNT_ID` y `ECR_REPOSITORY` para proteger la infraestructura sin comprometer la mantenibilidad.
