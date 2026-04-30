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