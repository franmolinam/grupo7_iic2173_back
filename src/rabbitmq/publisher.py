import pika
import json
from src.rabbitmq.utils import fibonacci_retry

# Aqui se usa el decorador del retry para evitar hacerlo cada vez que se publique un mensaje
@fibonacci_retry(max_retries=6)
def publicar_mensaje(channel, exchange, routing_key, message_dict):
    
    print(f"[*] Intentando publicar mensaje en {exchange} -> {routing_key}...")
    
    # Se usa basic_publish para enviar el mensaje y queda con el decorador
    channel.basic_publish(
        exchange=exchange,
        routing_key=routing_key,
        body=json.dumps(message_dict),
        mandatory=True 
    )
    print("[*] ¡Mensaje publicado exitosamente!")
    return True
