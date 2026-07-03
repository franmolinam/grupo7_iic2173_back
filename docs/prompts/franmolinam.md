# Prompts - Aoyonarte

## Flujo de conversación con Gemini - Backend CityExpress

### Resumen general
Se utilizó Gemini como asistente para el desarrollo del backend de CityExpress.

---

## Errores resueltos

### 1. 
**Prompt:** "Estoy obteniendo el siguiente error al conectar al broker: Error al conectar con RabbitMQ: 'NoneType' object has no attribute 'encode'"
**Respuesta:** Agregar la instrucción `env_file` apuntando al archivo `.env` en el docker-compose.yml.

### 2.
**Prompt:** "Obtengo el error: python: can't open file '/app/test_fibonacci.py': [Errno 2] No such file or directory"
**Respuesta:** Agregar archivos `__init__.py` para solucionar el tema de las rutas en el repositorio.

### 3.
**Prompt:** "Tengo el siguiente error al conectar: Error al conectar con RabbitMQ: Invalid isoformat string: '2026-04-29T04:54:07.302Z'"
**Respuesta:** "Z" al final significa "Zona UTC" (Zulu time). El problema es que las versiones de Python anteriores a la 3.11 no saben cómo leer esa "Z" cuando intentan convertir el texto a una fecha real para guardarla en la base de datos (usando la función interna fromisoformat). Python espera que diga +00:00 en lugar de Z.

### 4.
**Prompt:** "Debo enviar un mensaje de auditor cuando se recibe la tabla de distancias?"
**Respuesta:** No. El auditor de la central está diseñado exclusivamente para rastrear el ciclo de vida de los paquetes físicos.

### 5.
**Prompt:** "Una vez conectada por ssh a la ec2, como puedo revisar el estado del env?"
**Respuesta:** Una vez conectada por SSH: cat .env para solo ver el contenido. Si necesitas editarlo: nano .env.

### 6.
**Prompt:** "Sería necesario cambiar la db local a la de produccion para probar las suscripciones?"
**Respuesta** Sí, es necesario para resolver un problema de conectividad entre componentes: la API local (Docker en tu máquina) y el Lambda de Step Functions necesitan leer y escribir en la misma base de datos. El Lambda corre en AWS y solo puede conectarse a la BD de la EC2. No puede alcanzar tu BD Docker local (db:5432 en localhost). Entonces cuando la API creaba una suscripción en la BD local, el Lambda la buscaba en la BD de la EC2 y no la encontraba, fallando con UndefinedTable.
