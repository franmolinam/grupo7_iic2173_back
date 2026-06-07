# RDOC02: Integración con Webpay

## Descripción General
La integración con WebPay (portal de pagos de Transbank) se realizó en abiente de integración/pruebas usando las credenciales oficiales de tetsting de Transbank.

## Pasos implementados
### 1. Instalación del SDK
Se agregó `transbank-sdk` a `requirements.txt`.

### 2. Configuración del cliente Webpay
Se creó `src/services/webpay_service.py` con las credenciales de integración oficiales de Transbank:
- Commerce Code: 597055555532
- API Key: 579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C
- Ambiente: IntegrationType.TEST

Estas credenciales son públicas y proporcionadas por Transbank para pruebas.

### 3. Flujo de pago implementado
#### Paso 1: Cotización (`POST /shipments`)
El usuario crea una solicitud de envío mediante el endpoint `POST /shipments` indicando destino, dimensiones, criteria y maxHops. El sistema valida y calcula el precio final usando la fórmula dada en el enunciado:
Costo = max($5000, min($100.000, 0.01 * (h+w+d) * routeMetricCost * fprice))

#### Paso 2: Inicio de pago (`POST /shipments/:id/pay`)
El flujo es el siguiente:
1. Se crea una transacción en Webpay con tx.create(buy_order, session_id, amount, return_url)
2. Webpay devuelve un token y una url
3. Se guarda un Payment en BD con status TRYING.
4. Se envía mensaje de auditoría payment-status: TRYING al broker
5. Se retorna token y url al frontend

#### Paso 3: Redirección a Webpay (Frontend)
El frontend hace un form POST a la url de Webpay con el token como campo hidden token_ws. El usuario completa el pago en la interfaz de Transbank. 
[FRONTEND DOCUMENTA ESTE PASO]

#### Paso 4: Callback (`GET /payments/callback`)
Webpay redirige al usuario directamente a `WEBPAY_RETURN_URL?token_ws=...`. El backend tiene un endpoint `GET /payments/callback` que recibe ese token automáticamente, confirma con Transbank y procesa el resultado. El frontend solo necesita mostrar la página de resultado que devuelve el callback.
1. Si no viene token_ws significa que el usuario canceló, por lo que queda con status CANCELLED.
2. Si viene se confirma con Webpay usando tx.commit(token)
3. Si response_code == 0 significa pago exitoso y por lo que el status es SUCCESS, se actualiza la base de datos y se envía auditoría.
4. Si response_code != 0, el pago fue rechazado, el status queda en FAILED y se envía auditoría.

Nota: También esta creado el endpoint `POST /payments/callback` con `token_ws` en el body JSON `{"token_ws": "..."}` para casos donde el frontend necesite llamarlo directamente o para pruebas manuales.

### 4. Idempotencia
- El webpay_token tiene constraint UNIQUE en la tabla de payments, para asegurar que callbacks duplicados no se procesen dos veces.
- Si ya existe un pago TRYING para un shipment, se retorna 409.
- Si el callback llega con un token ya procesado (status SUCCESS o FAILED), se retorna el estado actual sin reprocesar.

### 5. Auditoría al broker
En cada estado se envía un mensaje payment-status al broker con el formato exigido por el enunciado, estados TRYING, SUCCESS y FAILED, y los campos adicionales routeMtricCost y maxHops para TRYING, authorizationCode y transactionDate para SUCCESS y reason: "REJECTED" para FAILED.

### 6. Variables de entorno necesarias
Es necesario incorporar al archivo .env la url del frontend:
`WEBPAY_RETURN_URL=https://eliasapi.me/payments/callback`

## Datos de tarjeta para pruebas en ambiente de integración
| Campo | Valor |
| :----- | :----- |
| Número | 4051 8856 0044 6623 |
| CVV | 123 |
| Expiración | Cualquier fecha futura |
| RUT | 11.111.111-1 |
| Clave banco | 123 |
