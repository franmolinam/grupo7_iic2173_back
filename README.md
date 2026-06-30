# Proyecto Semestral – CityExpress - Backend 

### **Nombre Grupo:** Grupo 7
### **Periodo:** IIC2173 2026-1

### Integrantes

| Nombre | Github | Email | 
| :----- | :----- | :---- |
| Camila Eguiguren Soza | [@Cami1010](https://github.com/Cami1010) | [ceguigurens@uc.cl](mailto:ferran.almeda@uc.cl) |
| Francisca Antonia Molina Milla | [@franmolinam](https://github.com/franmolinam) | [francisca.molina@uc.cl](mailto:francisca.molina@uc.cl) |
| Richard David Morrison Corrales | [@RichardUC](https://github.com/RichardUC) | [richardmc2003@uc.cl](mailto:richardmc2003@uc.cl) |
| Antonia Oyonarte Muñoz | [@aoyonarte](https://github.com/aoyonarte) | [aoyonarte@uc.cl](mailto:aoyonarte@uc.cl) |
| Elías Ezequiel Sarmiento Quezada | [@elias0006](https://github.com/elias0006) | [eliassarmiento@estudiante.uc.cl](mailto:eliassarmiento@estudiante.uc.cl) |

## Consideraciones Generales
**Nombre del dominio:** https://api.quackpackagemo.me/

**Método de acceso al servidor:**  
  - Archivo .pem: `key-ec2-cityexpress-api.pem`  
  - Permisos:  
    ```bash
    chmod 400 "key-ec2-cityexpress-api.pem"
    ```
  - Conexión SSH:  
    ```bash
    ssh -i "key-ec2-cityexpress-api.pem" ubuntu@ec2-13-59-84-29.us-east-2.compute.amazonaws.com
    ```

## Descripción de la solución

Esta entrega implementa una arquitectura distribuida basada en microservicios, donde cada ciudad opera como un nodo dentro de la red CityExpress.

## Puntos logrados E1
Requisitos Funcionales
- RF01 – Visualización de paquetes recibidos
- RF02 – Visualización de conectividad entre ciudades
- RF03 – Sistema de ruteo implementado
- RF04 – Entrega de paquetes con validación

Requisitos No Funcionales
- RNF01 – Separación Backend / Frontend
- RNF02 – Backend dockerizado y desplegado en EC2 usando ECR
- RNF03 – Configuración de Budget Alerts en AWS
- RNF04 – Implementacion de API Gateway con CORS
- RNF05 – Comunicación mediante HTTPS
- RNF06 – Autenticación implementada con Auth0
- RNF07 – Validación de tokens mediante Custom Authorizer
- RNF08 – Frontend desplegado en S3 + CloudFront
- RNF09 – New Relic: APM y monitoreo de infraestructura
- RNF10 – Reinicio automático de contenedores y retry con delay fibonacci

Documentación
- RDOC01 – Diagrama UML de Componentes
- RDOC02 – Monitoreo en New Relic
- RDOC03 – Procesos de ejecución.

## Puntos logrados E2
Requisitos Funcionales
- RF01 – Creación de solicitud de envío de paquete con validación de dimensiones, alcanzabilidad y saltos.
- RF02 – Cálculo y visualización de cotización antes del pago.
- RF03 – Validación de transacción mediante Webpay con manejo de estados e idempotencia.
- RF04 – Creación y envío de paquete al siguiente salto tras un pago exitoso.
- RF05 – Vista de usuario para revisión de envíos, pagos y estados de compra.
- RF06 – Sincronización y respuesta de tablas de distancia/costo entre ciudades.
- RF07 – Ruteo de paquetes según criterio de precio o distancia, respetando maxHops.
- RF08 – Acceso a la interfaz de administrador.

Requisitos No Funcionales
- RNF01 – Implementación de servicio asincrónico de jobs/workers para cálculo de rutas.
- RNF02 – Manejo robusto y persistencia de estados de pago de Webpay.
- RNF03 – Tolerancia a fallas en el ruteo distribuido.
- RNF04 – Indicador de disponibilidad del servicio de jobs/workers en el frontend administrador.
- RNF05 – Separación de permisos y vistas entre usuarios normales y administradores.
- RNF06 – Despliegue del sistema de workers en AWS utilizando Serverless Framework o AWS SAM.
- RNF07 – Persistencia de datos e implementación de idempotencia para pagos y paquetes.
- RNF08 – Pipeline CI/CD para backend usando AWS CodeDeploy y ECR. 
- RNF09 – Pipeline CI/CD para frontend con despliegue en AWS S3 y CloudFront.

Documentación
- RDOC01 – Diagrama UML de componentes actualizado.
- RDOC02 – Documentación de la integración con WebPay.
- RDOC03 – Documentación paso a paso del despliegue en Serverless/SAM.
- RDOC04 – Documentación explicativa del pipeline CI/CD.

## Puntos logrados E3
Requisitos Funcionales
- RF01 – Habilitación de entregas con suscripción para los usuarios en la UI utilizando AWS step functions.
- RF02 – Implementación de seguros para los paquetes, con opciones accesibles para los usuarios desde la interfaz.
- RF03 – Capacidad para que los usuarios puedan fijar la prioridad de entrega sobre los paquetes.
- RF04 – Implementación de un feed de eventos en tiempo real con SSE para el dashboard.

Requisitos No Funcionales
- RNF01 – Creación de alertas de observabilidad para detectar la falta de respuesta del frontend o backend, y el aumento de errores 500.
- RNF02 – Recreación de la infraestructura del backend como código (IaC) mediante Terraform cloud o AWS CDK con AWS cloud formation.
- RNF03 – Ejecución de Prowler cloud CLI y reparación de al menos 3 errores de seguridad de prioridad media o superior.
- RNF04 – Implementación de monitoreo con trazas funcionales sintéticas en la API principal, con visualización en un dashboard.
- RNF05 – Implementación de tests en los workflows de CI (linters y tests unitarios en backend; linters y Lighthouse en frontend) que validen y bloqueen el CD si no se cumplen.

Documentación
- RDOC01 – Actualización del diagrama UML de componentes incorporando los cambios de esta entrega, con detalles y explicaciones del sistema.
- RDOC02 – Documentación de los endpoints de la API expuestos al frontend mediante la generación de un archivo OpenAPI.

## Consideraciones Generales
- El proyecto fue desarrollado utilizando Docker desde el inicio.
- Se utilizó solo un .env para el manejo de configuraciones sensibles.
- La arquitectura fue diseñada priorizando separación de responsabilidades entre servicios.
- Se recomienda levantar primero el entorno local antes de desplegar en AWS.

## Bibliografía
1. [Python .gitignore template](https://github.com/github/gitignore/blob/main/Python.gitignore)
2. [Instalación de AWS CLI](https://docs.aws.amazon.com/es_es/cli/latest/userguide/getting-started-install.html)
3. [Desarrollo de las API HTTP en API Gateway](https://docs.aws.amazon.com/es_es/apigateway/latest/developerguide/http-api-develop.html)
4. [Configuración de CORS de las API de HTTP en API Gateway](https://docs.aws.amazon.com/es_es/apigateway/latest/developerguide/http-api-cors.html)
5. [Build and Secure a FastAPI Server with Auth0](https://auth0.com/blog/build-and-secure-fastapi-server-with-auth0/#Set-Up-an-Auth0-API)
6. [Setup Auth0 - FastAPI API](https://auth0.com/docs/quickstart/backend/fastapi)
7. [JSON Web Key Sets](https://auth0.com/docs/secure/tokens/json-web-tokens/json-web-key-sets)
8. [New Relic Python Agent Docs](https://docs.newrelic.com/docs/apm/agents/python-agent/getting-started/introduction-new-relic-python/)
9. [New Relic Infrastructure Monitoring](https://docs.newrelic.com/docs/infrastructure/infrastructure-agent/linux-installation/infra-agent-as-container/)
10. [Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
11. [NewRelic - Introduction to alerts](https://docs.newrelic.com/docs/alerts/overview/)
12. [NewRelic - Introduction to synthetic monitors](https://docs.newrelic.com/docs/synthetics/synthetic-monitoring/using-monitors/intro-synthetic-monitoring/)
13. [Prowler Cloud CLI - Installation](https://docs.prowler.com/getting-started/installation/prowler-cli#pip)
14. [AWS CDK - Documentation](https://docs.aws.amazon.com/es_es/cdk/?id=docs_gateway)

