import json
import pika
from src.rabbitmq.utils import fibonacci_retry

PRIORITY_MAP = {
    "low": 1,
    "medium": 2,
    "high": 3,
}

# Aqui se usa el decorador del retry para evitar hacerlo cada vez que se publique un mensaje
@fibonacci_retry(max_retries=6)
def publicar_mensaje(channel, exchange, routing_key, message_dict, priority: int = 1):
    print(f"[*] Intentando publicar mensaje en {exchange} -> {routing_key} (priority={priority})...")

    properties = pika.BasicProperties(
        delivery_mode=2,
        priority=priority,
    )
    
    # Se usa basic_publish para enviar el mensaje y queda con el decorador
    channel.basic_publish(
        exchange=exchange,
        routing_key=routing_key,
        body=json.dumps(message_dict),
        properties=properties,
        mandatory=True 
    )
    print("[*] ¡Mensaje publicado exitosamente!")
    return True
