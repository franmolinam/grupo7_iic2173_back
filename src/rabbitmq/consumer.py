from multiprocessing import context
import os
import pika
import ssl
import json 
from dotenv import load_dotenv
#import logging
#logging.basicConfig(level=logging.DEBUG)

# Cargar variables del .env
load_dotenv()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5671))
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD")
CODIGO_CIUDAD = os.getenv("CODIGO_CIUDAD")

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

        # Aqui hay que definir que hacer cuando llega un mensaje
        def callback(ch, method, properties, body):
            mensaje = json.loads(body)
            print(f"\n[x] ¡NUEVO MENSAJE RECIBIDO!")
            print(json.dumps(mensaje, indent=2))
        
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