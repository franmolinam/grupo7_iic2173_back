# RDOC01: Documentacion Diagrama de Componentes UML

## 1. AWS API Gateway
Es un `system`, porque es una entidad de infraestructura externa y gestionada que actúa como el punto de entrada principal a la red privada del grupo. Este recibe información del Frontend SPA a través de IPublicApi y entrega información al Nginx Proxy a través de ISecureTraffic.

### 1.1 HTTPS Endpoint
Es un `component`, porque representa el punto de enlace seguro que expone la interfaz pública de la API hacia el exterior. Este recibe información del Frontend SPA vía IClientData y entrega información al Gateway Logic vía IRequest.

### 1.2 Gateway Logic
Es un `component`, porque es la unidad de procesamiento encargada de gestionar el ruteo de peticiones y la integración con servicios de seguridad. Este recibe información del HTTPS Endpoint vía IRequest y entrega información al JWT / Custom Authorizer vía ITokenValidation.

### 1.3 JWT / Custom Authorizer
Es un `component`, porque es el módulo encargado de interceptar las peticiones para validar la autenticidad de los tokens con un proveedor externo. Este recibe información del Gateway Logic vía ITokenValidation y consulta las claves públicas al sistema Auth0 vía IPublicKeys, recibiendo de vuelta los claims del usuario vía IUserClaims.

## 2. Auth0
Es un `system`, porque es un servicio de terceros independiente encargado de la lógica de identidad y seguridad mediante tokens JWT. Provee la interfaz IPublicKeys al JWT / Custom Authorizer y al Auth Validator de la CityExpress API para la validación de tokens.

## 3. Nginx Proxy
Es un `system`, porque agrupa la lógica de servidor web y proxy inverso que orquesta el tráfico hacia los servicios internos del contenedor. Este recibe información del AWS API Gateway vía ISecureTraffic y entrega información al subsistema CityExpress API.

### 3.1 SSL/TLS Terminator
Es un `component`, porque es el encargado de gestionar el cifrado y descifrado de las comunicaciones. Este recibe información cifrada del AWS API Gateway y entrega información procesada al Reverse Proxy vía IInternalRequest.

### 3.2 Reverse Proxy Routing to API
Es un `subsystem`, porque agrupa la lógica de redirección de peticiones hacia los servicios internos. Este recibe información del SSL/TLS Terminator vía IInternalRequest y entrega las peticiones ya redirigidas al HTTP Controllers de la CityExpress API vía IProxiedRequest, que son recibidas a través de la interfaz IForwardedRequest.

## 4. CityExpress API
Es un `subsystem`, porque contiene la lógica de negocio, controladores HTTP, validaciones y gestión de pagos necesarias para cumplir con los requisitos funcionales de la aplicación. Este recibe peticiones del Nginx Proxy, persiste datos en la DB CityExpress vía IRepository, se comunica con Webpay (Transbank)
para el procesamiento de pagos, y delega el cálculo de rutas al JobsMaster vía IManageJobs.

### 4.1 HTTP Controllers
Es un `component`, porque es el módulo que gestiona las rutas de la API y procesa las solicitudes entrantes para los endpoints definidos. Recibe peticiones del Nginx Proxy vía IForwardedRequest y las delega a Auth Validator vía IAuthValidation, al Router de Paquetes vía IPackageRouting, a la Shipment Interface vía IShipmentOps,y al Payment Controller vía IIPaymentOps. Es instrumentado por el APM de New Relic a través de IAppMetrics.

### 4.2 Auth Validator
Es un `component`, porque es el encargado de verificar que el contexto de autorización sea válido antes de ejecutar lógica de negocio. Recibe solicitudes de validación del HTTP Controllers vía IAuthValidation y consulta las claves públicas a Auth0 vía IPublicKeys para verificar los tokens JWT.

### 4.3 Payment Controller
Es un `component`, porque encapsula toda la lógica del flujo de pago con Webpay: iniciación de transacción, manejo del callback, idempotencia y auditoría. Recibe solicitudes del HTTP Controllers vía IIPaymentOps, inicia transacciones en Webpay vía IInitPayment, recibe confirmaciones de Webpay vía IConfirmPayment, persiste el estado del pago en la DB CityExpress vía IRepository,y publica mensajes de auditoría al RabbitMQ Client vía IPublishAudit.

### 4.4 Router de Paquetes
Es una `interface`, porque define el contrato para consultar estados y gestionar la entrega de paquetes en tránsito. Recibe solicitudes del HTTP Controllers vía IPackageRouting y persiste o consulta datos en la DB CityExpress vía IRepository.

### 4.5 Shipment Interface
Es una `interface`, porque define el contrato para la creación de solicitudes de envío y el cálculo de cotizaciones. Recibe solicitudes del HTTP Controllers vía IShipmentOps y persiste los datos del envío en la DB CityExpress vía IRepository.

## 5. CityExpress Consumer
Es un `subsystem`, porque es un módulo especializado en el procesamiento asíncrono
de eventos de mensajería, ruteo de paquetes y sincronización de tablas de distancia. Recibe mensajes del Broker RabbitMQ, persiste datos en la DB CityExpress vía IDatabaseWriter, y publica mensajes de auditoría y reenvío de
vuelta al Broker vía IMessagePublisher.

### 5.1 RabbitMQ Client
Es un `component`, porque es el módulo de bajo nivel encargado de mantener la conexión y el protocolo de comunicación con el broker externo. Consume mensajes del Broker RabbitMQ vía IMessagePublisher, entrega los eventos al Event Handler vía IEventConsumer, consulta tiempos de reintento al Retry Delay Fibonacci vía IRetryDelay, persiste datos en la DB CityExpress vía IDatabaseWriter, y recibe mensajes de auditoría del Payment Controller vía IPublishAudit para publicarlos al broker.

### 5.2 Event Handler
Es una `interface`, porque es el procesador encargado de clasificar los mensajes recibidos (package-transit, distance-table, cost-update) y disparar las acciones correspondientes. Recibe eventos del RabbitMQ Client vía IEventConsumer.

### 5.3 Retry Delay Fibonacci
Es una `interface`, porque define el contrato para el cálculo de tiempos de espera exponenciales (Fibonacci) cuando falla el procesamiento de un evento. Provee la interfaz IRetryDelay al RabbitMQ Client.

## 6. DB CityExpress
Es la unidad de persistencia de datos (PostgreSQL) que encapsula el almacenamiento de paquetes, eventos, pagos, solicitudes de envío, rutas calculadas, tablas de distancia y jobs. Provee la interfaz IRepository a la
CityExpress API y sus componentes, la interfaz IDatabaseWriter al CityExpress Consumer, y la interfaz IRepository al Route Calculator de AWS Lambda Workers.

## 7. Broker RabbitMQ
Es un `system`, porque es la infraestructura de mensajería externa y compartida que coordina la red global de ciudades. Provee la interfaz IMessagePublisher al RabbitMQ Client para recibir mensajes publicados, y entrega mensajes al RabbitMQ Client (paquetes en tránsito, tablas de distancia, solicitudes de distance-table).

## 8. Webpay (Transbank)
Es un `system`, porque es el servicio externo de procesamiento de pagos utilizado para validar transacciones en ambiente de pruebas. Provee la interfaz IInitPayment al Payment Controller para iniciar transacciones y la interfaz IConfirmPayment para confirmar el resultado del pago.

## 9. JobsMaster
Es un `system`, porque es un servicio independiente encargado de coordinar el cálculo asíncrono de rutas óptimas mediante workers. Expone una API HTTP REST que recibe órdenes de la CityExpress API vía IManageJobs e invoca a los Lambda Workers vía IInvokeLambda.

### 9.1 Job API
Es un `component`, porque expone los endpoints REST del JobsMaster (POST /job, GET /job/:id, GET /heartbeat) para recibir y consultar trabajos de cálculo de rutas.

### 9.2 Job Tracker
Es un `component`, porque es el módulo encargado de registrar y mantener el estado de cada job (pending, running, completed, failed) a lo largo de su ciclo de vida.

## 10. AWS Lambda Workers
Es un `system`, porque agrupa las funciones serverless desplegadas en AWS Lambda mediante Serverless Framework, encargadas de ejecutar el cálculo de rutas de forma asíncrona y escalable.

### 10.1 Route Calculator
Es un `component`, porque implementa el algoritmo de cálculo de rutas óptimas (Dijkstra) para los criterios de distancia y precio. Es invocado por el JobsMaster vía IInvokeLambda y persiste los resultados en la DB CityExpress vía IRepository.

## 11. New Relic Agent
Es un `subsystem`, porque agrupa lógicamente las herramientas de observabilidad instaladas en el servidor. Se encarga de recolectar telemetría tanto del código como del hardware para enviarla a New Relic SaaS.

### 11.1 Application Performance Monitoring (APM)
Es un `subsystem`, porque es la herramienta encargada de recolectar métricas de tiempo de respuesta y errores de los controladores. Instrumenta el HTTP Controllers vía IAppMetrics y entrega los datos recolectados a New Relic SaaS vía ITelemetryData.

### 11.2 Infrastructure Monitoring
Es un `subsystem`, porque es el encargado de vigilar el estado de salud de la instancia EC2 y la utilización de recursos de los contenedores. Entrega métricas de infraestructura a New Relic SaaS vía IInfraMetrics.

## 12. New Relic SaaS
Es un `system` externo gestionado en la nube que recibe, procesa y visualiza las métricas de toda la infraestructura y la aplicación. Recibe datos de performance del APM vía ITelemetryData y métricas de infraestructura del Infrastructure Monitoring vía IInfraMetrics.

## 13. AWS ECR Instance
Es un `system`, porque es el registro de contenedores de AWS que almacena y distribuye las imágenes Docker de la aplicación. Contiene el Docker Image que se despliega en la instancia EC2 vía IImageDeployment.

## Interfaces principales del sistema

### IForwardedRequest
Es la interfaz que provee el Reverse Proxy Routing to API al HTTP Controllers, representando las peticiones HTTP ya redirigidas hacia la red interna.

### IAuthValidation
Es la interfaz que provee el Auth Validator al HTTP Controllers para la verificación de tokens JWT antes de ejecutar lógica de negocio.

### IRepository
Es la interfaz que provee la DB CityExpress a la CityExpress API (Router de Paquetes, Shipment Interface, Payment Controller) y al Route Calculator para operaciones de lectura y escritura de datos.

### IManageJobs
Es la interfaz REST que provee el JobsMaster a la CityExpress API para crear jobs de cálculo de rutas y consultar su estado.

### IInvokeLambda
Es la interfaz que provee AWS Lambda Workers al JobsMaster para la invocación de funciones de cálculo de rutas.

### IMessagePublisher
Es la interfaz que provee el Broker RabbitMQ al RabbitMQ Client para la publicación y consumo de mensajes en el sistema de mensajería distribuido.

### IPublishAudit
Es la interfaz que provee el RabbitMQ Client al Payment Controller para publicar mensajes de auditoría de pagos (payment-status) al broker.