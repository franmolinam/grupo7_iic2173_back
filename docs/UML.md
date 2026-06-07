# RDOC01: Documentacion Diagrama de Componentes UML

## 1. AWS API Gateway
Es un `system`, porque es una entidad de infraestructura externa y gestionada que actúa como el punto de entrada principal a la red privada del grupo. Este recibe información del Frontend SPA y entrega información al Nginx Proxy.

### 1.1 HTTPS Endpoint
Es un `component`, porque representa el punto de enlace seguro que expone la interfaz pública de la API hacia el exterior. Este recibe información del Frontend SPA y entrega información al Gateway Logic.

### 1.2 Gateway Logic
Es un `component`, porque es la unidad de procesamiento encargada de gestionar el ruteo de peticiones y la integración con servicios de seguridad. Este recibe información del HTTPS Endpoint y entrega información al JWT / Custom Authorizer o al Reverse Proxy Routing to API.

### 1.3JWT / Custom Authorizer
Es un `component`, porque es el módulo encargado de interceptar las peticiones para validar la autenticidad de los tokens con un proveedor externo. Este recibe información del Gateway Logic y entrega información al sistema Auth0.

## 2. Auth0 / Custom Authorizer
Es un `system`, porque es un servicio de terceros independiente encargado de la lógica de identidad y seguridad mediante tokens JWT. Este recibe información del AWS API Gateway y CityExpress Api, y devuelve la información al AWS API Gateway.  

## 3.Nginx Proxy
Es un `system`, porque agrupa la lógica de servidor web y proxy inverso que orquesta el tráfico hacia los servicios internos del contenedor. Este recibe información del AWS API Gateway y entrega información al componente CityExpress API.

### 3.1 Reverse Proxy
Es un `component`, porque es la unidad funcional encargada de recibir las peticiones externas y redirigirlas a la red interna de contenedores. Este recibe información del AWS API Gateway y entrega información al componente HTTP Controllers de la API.

### 3.2 SSL/TLS Terminator
Es un `component`, porque es el encargado de gestionar el cifrado y descifrado de las comunicaciones. Este recibe información cifrada del AWS API Gateway y entrega información procesada al Reverse Proxy.

## 4. CityExpress API
Es un `subsystem`, porque contiene la lógica de negocio, controladores HTTP y validaciones necesarias para cumplir con los requisitos funcionales de consulta y entrega. Este recibe información del Nginx Proxy y del DB CityExpress, y entrega información a New Relic Agent.

### 4.1 HTTP Controllers
Es un `component`, porque es el módulo que gestiona las rutas de la API y procesa las solicitudes entrantes para los endpoints definidos. Este recibe información del Nginx Proxy y entrega información al Auth Validator y a New Relic Agent.

### 4.2 Auth Validator
Es un `component`, porque es el encargado de verificar internamente que el contexto de autorización sea válido antes de ejecutar lógica de negocio. Este recibe información del HTTP Controllers y entrega información al Router de Paquetes y a Auth0.

### 4.3 Router de Paquetes
Es una `interface`, porque implementa la lógica necesaria para consultar estados y gestionar la entrega de paquetes. Este recibe información del Auth Validator y de la DB CityExpress, y entrega la información procesada de vuelta a los HTTP Controllers para que construyan la respuesta final hacia el cliente.

## 5. CityExpress Consumer
Es un `subsystem`, porque es un módulo especializado en el procesamiento asíncrono de eventos de mensajería y ruteo dimensional. Este recibe información del Broker RabbitMQ (Central) y entrega información de auditoría al Broker RabbitMQ (Central) y datos persistentes a la DB CityExpress. 

### 5.1 RabbitMQ Client
Es un `component`, porque es el módulo de bajo nivel encargado de mantener la conexión y el protocolo de comunicación con el broker externo. Este recibe información del Broker RabbitMQ (Central) y entrega información al Event Handler.

### 5.2 Event Handler
Es un `interface`, porque es el procesador encargado de clasificar los mensajes recibidos (package-transit o distance-table) y disparar las acciones correspondientes. Este recibe información del RabbitMQ Client y entrega información a la DB CityExpress para actualización de estados.

### 5.3 Lógica de Reintentos (Fibonacci)
Es un `component` encargado de calcular los tiempos de espera exponenciales cuando falla el procesamiento de un evento. Recibe solicitudes del RabbitMQ Client y le devuelve el tiempo exacto que debe retrasar el mensaje.

## 6. DB CityExpress
Es un `component`, porque es una unidad de persistencia de datos (PostgreSQL) que encapsula el almacenamiento del estado de paquetes y rutas. Este recibe peticiones de escritura/lectura de la CityExpress API y del CityExpress Consumer, y les devuelve los registros solicitados.  

## 7. Broker RabbitMQ (Central)
Es un `system`, porque es la infraestructura de mensajería externa y compartida que coordina la red global de ciudades. Este recibe información del CityExpress Consumer (Auditoría/Reenvío) y entrega información al CityExpress Consumer (Paquetes/Tablas de distancia).

## 8 New Relic Agent
Es un `subsystem`, porque agrupa lógicamente las herramientas de observabilidad instaladas localmente en el servidor. Este pertenece al sistema AWS EC2 y se encarga de recolectar la telemetría tanto del código como del hardware para enviarla a la nube.


### 8.1 Application Performance Monitoring (APM)
Es un `subsystem`, porque es la herramienta encargada de recolectar métricas de tiempo de respuesta y errores de los controladores. Este pertenece al sistema AWS EC2 Instance / Docker Network y al subsistema New Relic Agent. Este recibe información de la CityExpress API y entrega información al sistema externo New Relic SaaS.

### 8.2 Infrastructure Monitoring
Es un `subsystem`, porque es el encargado de vigilar el estado de salud de la instancia EC2 y la utilización de recursos de los contenedores. Este pertenece al sistema AWS EC2 Instance / Docker Network y al subsistema New Relic Agent. Este recibe información de la AWS EC2 Instance y entrega información al sistema externo New Relic SaaS.

## 8.3 New Relic SaaS
Es un system externo gestionado en la nube que recibe, procesa y visualiza las métricas de toda la infraestructura y la aplicación. Recibe información de telemetría a través de su API desde el Application Performance Monitoring (APM) y el Infrastructure Monitoring.

### Interfaz REST (HTTP)
Es una `interface`, porque define el contrato de comunicación y los métodos permitidos entre el cliente y el servidor. Este pertenece al sistema CityExpress. Esta recibe información del Frontend SPA y entrega información a la CityExpress API.  

### Interfaz AMQP (Messaging)
Es una `interface`, porque establece el protocolo de intercambio de mensajes, colas y bindings para la red de portales. Este pertenece al sistema CityExpress. Esta recibe información del Broker RabbitMQ y entrega información al CityExpress Consumer.