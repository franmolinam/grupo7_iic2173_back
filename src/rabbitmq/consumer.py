import os
import pika
import ssl
import json
import uuid
from datetime import datetime, timezone 
from publisher import publicar_mensaje
from dotenv import load_dotenv

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
        heartbeat=60 # Esta linea mantiene viva la conexion
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
                
                # Ack del broker
                # Una vez procesado, se debe borrar de la cola
                ch.basic_ack(delivery_tag=method.delivery_tag)
                print(f"[*] Mensaje procesado. ACK/NACK enviado a: {routing_key_destino}")

            except json.JSONDecodeError:
                # Caso en que el mensaje no es un JSON valido
                print("[!] Error: El cuerpo del mensaje no es un JSON valido.")
                # basic_nack al broker le dice que hubo un error
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        print(f"[*] Conexion exitosa. Esperando mensajes en la cola: {nombre_cola}")

        # Iniciar la escucha
        channel.basic_consume(
            queue=nombre_cola, 
            on_message_callback=callback, 
            auto_ack=False # Es importante dejar esto en False porque se implementa ACK/NACK manual
        )
        
        channel.start_consuming()

    except Exception as e:
        print(f"[!] Error al conectar con RabbitMQ: {e}")

# Para probar este script directamente de forma local
if __name__ == "__main__":
    start_consumer()