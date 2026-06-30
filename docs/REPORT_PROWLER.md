# RNF03 (E3): Reporte de Auditoría de Seguridad con Prowler

## Datos Generales
**Fecha de ejecución:** 27 de Junio de 2026
**Fecha de resolución:** 29 de Junio de 2026
**Herramienta utilizada:** Prowler Cloud CLI  
**Objetivo:** Identificar y remediar al menos 3 vulnerabilidades de seguridad de prioridad *Medium* o superior en la infraestructura de AWS.


## 1. Vulnerabilidad 1: Política de contraseñas de IAM débil
- **Nivel de Severidad:** 🟡 Medium
- **ID del Error:** iam_password_policy_minimum_length_14
- **Servicio de AWS:** IAM
- **Descripción del problema:** No se exige un mínimo de 14 caracteres ni símbolos en las contraseñas de los usuarios.
- **Solución aplicada:** Se modificó la política de contraseñas de la cuenta desde la consola de IAM para exigir al menos un símbolo, un número y 14 caracteres de longitud.

### Evidencia de la corrección
![Evidencia 1](./images/new_iam_parameters.png)


## 2. Vulnerabilidad 2: Falta de cifrado por defecto en volúmenes EBS
- **Nivel de Severidad:** 🟡 Medium
- **ID del Error:** ec2_ebs_default_encryption
- **Servicio de AWS:** Amazon EC2
- **Descripción del problema:** La cuenta de AWS no tiene habilitado el cifrado por defecto para los volúmenes de almacenamiento (EBS), lo que podría permitir la creación de nuevos discos sin cifrado, exponiendo los datos en reposo.
- **Solución aplicada:** Se ingresó al panel de control de EC2, en la sección de atributos de la cuenta, y se activó la opción de habilitar el cifrado de EBS por defecto.

### Evidencia de la corrección
![Evidencia 2](./images/ebs_encryption.png)


## 3. Vulnerabilidad 3: Falta de expiracion obligatoria de contraseñas
- **Nivel de Severidad:** 🟡 Medium
- **ID del Error:** iam_password_policy_expires_passwords_within_90_days
- **Servicio de AWS:** IAM
- **Descripción del problema:** La política de contraseñas de la cuenta no exige que las contraseñas expiren cada 90 días o menos, lo cual aumenta el riesgo de que credenciales comprometidas sean usadas prolongadamente.
- **Solución aplicada:** Se editó la política de contraseñas en ``IAM > Account settings`` para habilitar la expiración obligatoria (``Enable password expiration``) configurándola a 90 días.

### Evidencia de la corrección
![Evidencia 3](./images/new_iam_parameters.png)


## Logs - Prowler Cloud CLI
Se mostraran lo logs generados por Prowler para cada tipo de error y despues de su correcion.
El archivo HTML original generado por Prowler se encuentra adjunto en este repositorio en la ruta

## Vulnerabilidad 1
### Log Inicial
![Log Inicial - Vulnerabilidad 1](./images/prowler_error_iam_password_policy_minimum_length_14.png)
### Log Final
![Log Final - Vulnerabilidad 1](./images/prowler_pass_iam_password_policy_minimum_length_14.png)


## Vulnerabilidad 2
### Log Inicial
![Log Inicial - Vulnerabilidad 2](./images/prowler_error_ec2_ebs_default_encryption.png)
### Log Final
![Log Final - Vulnerabilidad 2](./images/prowler_pass_ec2_ebs_default_encryption.png)


## Vulnerabilidad 3
### Log Inicial
![Log Inicial - Vulnerabilidad 3](./images/prowler_error_iam_password_policy_expires_passwords_within_90_days.png)
### Log Final
![Log Final - Vulnerabilidad 3](./images/prowler_pass_iam_password_policy_expires_passwords_within_90_days.png)

