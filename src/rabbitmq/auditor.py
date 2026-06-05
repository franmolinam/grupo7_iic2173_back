import os
import uuid
from datetime import datetime, timezone
from src.rabbitmq.publisher import publicar_mensaje

# Se carga el codigo de la ciudad desde el .env
CODIGO_CIUDAD = os.getenv("CODIGO_CIUDAD")

# Esta funcion se encarga de enviar los distintos tipos de reportes a la central
def enviar_reporte_auditor(channel, package_id, tipo_reporte, next_city_id=None):
    mensaje_auditor = {
        "idpk": str(uuid.uuid4()),
        "msgId": str(uuid.uuid4()),
        "type": tipo_reporte,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cityId": CODIGO_CIUDAD,
        "pkgId": package_id
    }

    # Al ser un reenvio, se exige que vaya dentro del bloque data
    if tipo_reporte in ["transit", "transit-redirect"] and next_city_id:
        mensaje_auditor["data"] = {
            "nextCityId": next_city_id
        }

    print(f"[*] Auditor: Notificando a la central que paquete {package_id} está '{tipo_reporte}'")
    
    publicar_mensaje(
        channel=channel,
        exchange='fulfillment.x',
        routing_key='central',
        message_dict=mensaje_auditor
    )

def enviar_auditoria_pago(
    payment_id: str,
    pkg_id: str,
    token: str,
    status: str,
    amount: int,
    destination_id: str = None,
    criteria: str = None,
    route_metric_cost: float = None,
    max_hops: int = None,
    authorization_code: str = None,
    transaction_date: str = None,
    reason: str = None,
):
    data = {
        "status": status,
        "paymentId": payment_id,
        "amount": amount,
        "currency": "CLP",
        "destinationId": destination_id,
        "criteria": criteria,
    }

    if status == "TRYING":
        data["routeMetricCost"] = route_metric_cost
        data["maxHops"] = max_hops
    elif status == "SUCCESS":
        data["authorizationCode"] = authorization_code
        data["transactionDate"] = transaction_date
    elif status == "FAILED":
        data["reason"] = reason

    mensaje = {
        "idpk": str(uuid.uuid4()),
        "msgId": str(uuid.uuid4()),
        "type": "payment-status",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cityId": CODIGO_CIUDAD,
        "pkgId": pkg_id,
        "payment_token": token,
        "data": data,
    }

    print(f"[*] Auditor: Enviando payment-status '{status}' para pago {payment_id}")

    # Necesitamos un channel
    import pika, ssl, os
    credenciales = pika.PlainCredentials(
        os.getenv("RABBITMQ_USER"), os.getenv("RABBITMQ_PASSWORD")
    )
    context = ssl.create_default_context()
    ssl_options = pika.SSLOptions(context)
    parameters = pika.ConnectionParameters(
        host=os.getenv("RABBITMQ_HOST"),
        port=int(os.getenv("RABBITMQ_PORT", 5671)),
        virtual_host="fulfillment",
        credentials=credenciales,
        ssl_options=ssl_options,
        heartbeat=60,
    )
    conexion = pika.BlockingConnection(parameters)
    channel = conexion.channel()

    publicar_mensaje(
        channel=channel,
        exchange="fulfillment.x",
        routing_key="central",
        message_dict=mensaje,
    )
    conexion.close()