# Proyecto Semestral – CityExpress - Backend (IIC2173 2026-1)

## **Nombre Grupo:** Grupo7

### Integrantes

| Nombre | Github | Email | 
| :----- | :----- | :---- |
| Camila Eguiguren Soza | [@Cami1010](https://github.com/Cami1010) | [ceguigurens@uc.cl](mailto:ferran.almeda@uc.cl) |
| Francisca Antonia Molina Milla | [@franmolinam](https://github.com/franmolinam) | [francisca.molina@uc.cl](mailto:francisca.molina@uc.cl) |
| Richard David Morrison Corrales | [@RichardUC](https://github.com/RichardUC) | [richardmc2003@uc.cl](mailto:richardmc2003@uc.cl) |
| Antonia Oyonarte Muñoz | [@aoyonarte](https://github.com/aoyonarte) | [aoyonarte@uc.cl](mailto:aoyonarte@uc.cl) |
| Elías Ezequiel Sarmiento Quezada | [@elias0006](https://github.com/elias0006) | [eliassarmiento@estudiante.uc.cl](mailto:eliassarmiento@estudiante.uc.cl) |

## Consideraciones Generales
<!-- Cambiar para cuando se tenga la información-->
- **Nombre del dominio:** api.<miapp>.com
- **Método de acceso al servidor:**  
  - Archivo `.pem`: `<nombre-key>.pem`  
  - Permisos:  
    ```bash
    chmod 400 "<nombre-key>.pem"
    ```
  - Conexión SSH:  
    ```bash
    ssh -i "<nombre-key>.pem" ubuntu@<ec2-public-dns>
    ```

---

## Descripción de la solución

Esta entrega implementa una arquitectura distribuida basada en microservicios, donde cada ciudad opera como un nodo dentro de la red CityExpress.

## Puntos logrados
<!-- Todos los pasos no logrados quedaran comentados, si son cumplidos descomentelos.
Tambien consideren que algunos son del frontend
Un acceso rapido para hacerlo es Shift + Alt + A -->
Requisitos Funcionales
<!-- - RF01 – Visualización de paquetes recibidos -->
<!-- - RF02 – Visualización de conectividad entre ciudades -->
<!-- - RF03 – Sistema de ruteo implementado -->
<!-- - RF04 – Entrega de paquetes con validación -->
Requisitos No Funcionales
<!-- - RNF01 – Separación Backend / Frontend -->
<!-- - RNF02 – Backend dockerizado y desplegado en EC2 usando ECR -->
<!-- - RNF03 – Configuración de Budget Alerts en AWS -->
<!-- - RNF04 – Implementacion de API Gateway con CORS -->
<!-- - RNF05 – Comunicación mediante HTTPS -->
<!-- - RNF06 – Autenticación implementada con Auth0 -->
<!-- - RNF07 – Validación de tokens mediante Custom Authorizer -->
<!-- - RNF08 – Frontend desplegado en S3 + CloudFront -->
<!-- - RNF09 – New Relic: APM y monitoreo de infraestructura -->
<!-- - RNF10 – Reinicio automático de contenedores y retry con delay fibonacci -->
Documentación
<!-- - RDOC01 – Diagrama UML de Componentes -->
<!-- - RDOC02 – Monitoreo en New Relic -->
<!-- - RDOC03 – Procesos de ejecución. -->

---

## Consideraciones Generales
<!-- Revisar si todo esta bien -->
- El proyecto fue desarrollado utilizando Docker desde el inicio.
- Se utilizó .env para manejo de configuración sensible (no versionado).
- La arquitectura fue diseñada priorizando separación de responsabilidades entre servicios.
- Se recomienda levantar primero el entorno local antes de desplegar en AWS.