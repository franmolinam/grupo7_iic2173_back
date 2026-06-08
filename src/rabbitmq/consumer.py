import os
import traceback
import pika
import ssl
import json
import uuid
from datetime import datetime, timezone 
from src.rabbitmq.publisher import publicar_mensaje
from src.rabbitmq.auditor import enviar_reporte_auditor
from dotenv import load_dotenv
from src.handlers.package_handler import (
    handle_package_received, 
    handle_package_forwarded, 
    handle_package_expired,
    handle_distance_table,
    get_local_distance_table
)

from src.database import SessionLocal

# Cargar variables del .env
load_dotenv()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5671))
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD")
CODIGO_CIUDAD = os.getenv("CODIGO_CIUDAD")

# Esta funcion es para determinar si el mensaje viene bien formado
def validar_mensaje(mensaje_dict):
    campos_requeridos = ["idpk", "msgId", "type", "timestamp"]
    for campo in campos_requeridos:
        if campo not in mensaje_dict:
            return False
    return True

def start_consumer():
    # Primero se configuran las credenciales y el contexto SSL
    credenciales = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    context = ssl.create_default_context()
    ssl_options = pika.SSLOptions(context)

    # Luego se definen los parametros de conexión
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        virtual_host="fulfillment",
        credentials=credenciales,
        ssl_options=ssl_options,
        heartbeat=60, # Esta linea mantiene viva la conexion
    )

    try:
        # Conexion al broker
        print(f"[*] Conectando al broker en {RABBITMQ_HOST}...")
        conexion = pika.BlockingConnection(parameters)
        channel = conexion.channel()
        nombre_cola = f"city.{CODIGO_CIUDAD}.q"

        # Aqui se define que hacer cuando llega un mensaje
        def callback(ch, method, properties, body):
            try:
                mensaje = json.loads(body)

                #print(json.dumps(mensaje, indent=2)) #Por si se necesita ver el mensaje recibido

                # Con esto se evita un loop infinito 
                if mensaje.get("type") in ["ack", "nack"]:
                    print("[*] El mensaje es un ACK/NACK. Se limpia de la cola y no se responde.")
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return
                
                # El primer paso es validar el mensaje
                es_valido = validar_mensaje(mensaje)
                
                # El segundo paso es preparar la respuesta
                ciudad_origen = mensaje.get("cityId")
                
                # Si no viene ciudad de origen, se busca dentro del paquete
                if not ciudad_origen:
                    cuerpo = mensaje.get("body") or mensaje.get("packageBody", {})
                    ciudad_origen = cuerpo.get("originId", "Desconocido")
                
                print(f"\n[x] ¡NUEVO MENSAJE RECIBIDO DE: {ciudad_origen}!")

                if ciudad_origen != "Desconocido":
                    respuesta = {
                        "idpk": str(uuid.uuid4()),
                        "msgId": str(uuid.uuid4()),
                        "type": "ack" if es_valido else "nack",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "cityId": CODIGO_CIUDAD,
                        "replyToMsgId": mensaje.get("msgId") # Referencia al mensaje original
                    }
                    
                    # Si viene de "central", se responde a "central". Si es ciudad, a "city.codigo"
                    if ciudad_origen.lower() == "central":
                        routing_key_destino = "central"
                    else:
                        routing_key_destino = f"city.{ciudad_origen.lower()}"
                    
                    # Se usa el publicador con retry
                    publicar_mensaje(
                        channel=ch,
                        exchange='fulfillment.x', 
                        routing_key=routing_key_destino,
                        message_dict=respuesta
                    )

                    print(f"[*] ACK/NACK enviado a: {routing_key_destino}")
                
                # Se procesa si el mensaje es de tipo package-transit
                if mensaje.get("type") == "package-transit":
                    db = SessionLocal() # Abrir conexion a la DB
                    try:
                        cuerpo = mensaje.get("body") or mensaje.get("packageBody", {})
                        
                        # Aqui se remplaza la "Z" por "+00:00" para que SQLAlchemy no se caiga
                        for campo_fecha in ["createdAt", "expiresAt", "deliverNotBefore"]:
                            if campo_fecha in cuerpo and isinstance(cuerpo[campo_fecha], str) and cuerpo[campo_fecha].endswith("Z"):
                                cuerpo[campo_fecha] = cuerpo[campo_fecha].replace("Z", "+00:00")

                        # Aqui se llama al package_handler
                        resultado = handle_package_received(
                            db=db,
                            package_body=cuerpo,
                            received_from=ciudad_origen
                        )
                        
                        accion = resultado["action"]
                        
                        # No se reenvia, se queda en la DB para que el Frontend lo entregue.
                        if accion == "deliver":
                            print(f"[*] Paquete {resultado['package_id']} es para LSN. Queda pendiente de entrega local.")
                            enviar_reporte_auditor(ch, resultado['package_id'], "received")
                        
                        elif accion == "expire":
                            print(f"[*] Paquete {resultado['package_id']} expiró (maxHops=0).")
                            handle_package_expired(db, resultado['package_id'])
                            enviar_reporte_auditor(ch, resultado['package_id'], "expired")
                        
                        elif accion == "pending_routing":
                            print(f"[*] Paquete {resultado['package_id']} se quedó sin ruta hacia {cuerpo.get("destinationId", "").upper()}. Guardado como pending-routing.")

                        # Reenvio a otra ciudad
                        elif accion == "forward":
                            siguiente_ciudad = resultado["destination_id"].lower()
                            print(f"[*] Reenviando paquete {resultado['package_id']} hacia {siguiente_ciudad}...")
                            
                            # Descuento de maxHops y preparacion
                            cuerpo_modificado = cuerpo.copy()
                            cuerpo_modificado["maxHops"] = resultado["max_hops_remaining"]
                            
                            paquete_reenvio = {
                                "idpk": str(uuid.uuid4()),
                                "msgId": str(uuid.uuid4()),
                                "type": "package-transit",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "cityId": CODIGO_CIUDAD, # El origen ahora es la propia ciudad
                                "body": cuerpo_modificado
                            }
                            
                            # Paquete a la ciudad destino
                            publicar_mensaje(
                                channel=ch,
                                exchange='fulfillment.x',
                                routing_key=f"city.{siguiente_ciudad}",
                                message_dict=paquete_reenvio
                            )
                            
                            # Aviso a la DB que el reenvio fue exitoso
                            handle_package_forwarded(db, resultado["package_id"], siguiente_ciudad)
                            enviar_reporte_auditor(ch, resultado['package_id'], "transit", siguiente_ciudad)

                    finally:
                        db.close() # Cerrar la sesión de DB
                
                # Se procesa si el mensaje es de tipo cost-update
                elif mensaje.get("type") == "cost-update":
                    db = SessionLocal()
                    try:
                        print("[*] Procesando actualizacion de tabla de distancias/costos...")
                        # Primero se obtiene el contenido
                        body_data = mensaje.get("body", {})
                        rutas = body_data.get("routes", [])

                        distancias_formateadas = {}

                        # Central o de otra ciudad
                        origen_real = body_data.get("cityCode") if "cityCode" in body_data else ciudad_origen

                        if rutas:
                            # Convertir el arreglo 'routes' al formato de diccionario que espera tu DB
                            for ruta in rutas:
                                distancias_formateadas[ruta["destinationCode"]] = ruta
                        else:
                            distancias_formateadas = mensaje.get("data", {}).get("distances", {})
                        
                        if distancias_formateadas and origen_real!="Desconocido":
                            handle_distance_table(db, CODIGO_CIUDAD, distancias_formateadas)
                            print("[*] Tabla de distancias actualizada exitosamente en la base de datos")
                            
                            # Si la tabla viene de la central, se piden la tablas de las demas ciudades
                            if "cityCode" in body_data: 
                                print("[*] Nueva tabla de la central. Solicitando tablas a las otras ciudades...")
                                request_distancias = {
                                    "idpk": str(uuid.uuid4()),
                                    "msgId": str(uuid.uuid4()),
                                    "type": "request",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "source": CODIGO_CIUDAD,
                                    "data": {
                                        "ask": "distance-table"
                                    }
                                }
                                
                                # Luego se itera sobre las ciudades de la tabla guardada para enviarles el request
                                for destino in distancias_formateadas.keys():
                                    if destino.upper() != CODIGO_CIUDAD.upper():
                                        publicar_mensaje(
                                            channel=ch,
                                            exchange='fulfillment.x',
                                            routing_key=f"city.{destino.lower()}",
                                            message_dict=request_distancias
                                        )
                        else:
                            print("[!] Advertencia: El mensaje cost-update no contiene datos validos.")
                    finally:
                        db.close()
                
                # Cuando otra ciudad pide la tabla de distancias
                elif mensaje.get("type") == "request" and mensaje.get("data", {}).get("ask") == "distance-table":
                    db = SessionLocal()
                    try:
                        ciudad_solicitante = mensaje.get("source") or mensaje.get("cityId") or "Desconocido"

                        if ciudad_solicitante == "Desconocido":
                             print("[!] Advertencia: Solicitud de tabla sin 'source' ni 'cityId'. Ignorando.")
                             ch.basic_ack(delivery_tag=method.delivery_tag)
                             return

                        print(f"[*] Solicitud de tabla recibida de: {ciudad_solicitante}. Preparando respuesta...")

                        # Se prepara y publica el mensaje ACK
                        respuesta_ack = {
                            "idpk": str(uuid.uuid4()),
                            "msgId": str(uuid.uuid4()),
                            "type": "ack",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "cityId": CODIGO_CIUDAD,
                            "replyToMsgId": mensaje.get("msgId") # Referencia al mensaje original
                        }

                        publicar_mensaje(
                            channel=ch,
                            exchange='fulfillment.x',
                            routing_key=f"city.{ciudad_solicitante.lower()}",
                            message_dict=respuesta_ack
                        )
                        print(f"[*] ACK enviado a {ciudad_solicitante} por solicitud de tabla de distancias.")

                        # Primero se obtiene la tabla local
                        local_distances = get_local_distance_table(db)
                        
                        # Se arma el mensaje de respuesta tipo cost-update
                        respuesta_costos = {
                            "idpk": str(uuid.uuid4()),
                            "msgId": str(uuid.uuid4()),
                            "type": "cost-update",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "cityId": CODIGO_CIUDAD,
                            "data": {
                                "distances": local_distances
                            }
                        }
                        
                        # Se envia directamente a la ciudad que la pidio
                        publicar_mensaje(
                            channel=ch,
                            exchange='fulfillment.x',
                            routing_key=f"city.{ciudad_origen.lower()}",
                            message_dict=respuesta_costos
                        )
                        print(f"[*] Tabla de distancias ha sido enviada a {ciudad_origen}.")
                    finally:
                        db.close()
                
                # Ack del broker
                # Una vez procesado, se debe borrar de la cola
                ch.basic_ack(delivery_tag=method.delivery_tag)
                print(f"[*] Mensaje procesado y retirado de la cola.")

            except json.JSONDecodeError:
                # Caso en que el mensaje no es un JSON valido
                print("[!] Error: El cuerpo del mensaje no es un JSON valido.")
                # basic_nack al broker le dice que hubo un error
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        # Iniciar la escucha
        channel.basic_consume(
            queue=nombre_cola, 
            on_message_callback=callback, 
            auto_ack=False # Es importante dejar esto en False porque se implementa ACK/NACK manual
        )

        # Se solicita la tabla de distancias al iniciar el consumidor
        # Despues solo se reciben updates        
        print("[*] Solicitando tabla de distancias inicial a la central...")
        request_distancias = {
            "idpk": str(uuid.uuid4()),
            "msgId": str(uuid.uuid4()),
            "type": "request",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cityId": CODIGO_CIUDAD,
            "data": {
                "ask": "distance-table"
            }
        }

        # Enviar peticion
        publicar_mensaje(
            channel=channel,
            exchange='fulfillment.x',
            routing_key='central', 
            message_dict=request_distancias
        )
        print("[*] Peticion de tabla de distancias enviada.")

        print(f"[*] Conexion exitosa. Esperando mensajes en la cola: {nombre_cola}")

        channel.start_consuming()

    except Exception as e:
        print(f"[!] Error al conectar con RabbitMQ: {repr(e)}")
        traceback.print_exc()

# Para probar este script directamente de forma local
if __name__ == "__main__":
    start_consumer()