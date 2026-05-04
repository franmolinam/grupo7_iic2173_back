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
