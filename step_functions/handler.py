# Este archivo es para manejar las funciones Lambda que se usan en la state machine de suscripciones
"""
Lambda handlers para la state machine de entregas con suscripción.

Dos funciones:
  check_subscription  — verifica si la suscripción debe continuar (budget y cantidad).
  execute_delivery    — crea y envía un paquete vía RabbitMQ y actualiza la suscripción.
"""

import json
import os
import ssl
import uuid
from datetime import datetime, timezone

import pika
import psycopg2
from psycopg2.extras import RealDictCursor

CODIGO_CIUDAD = os.getenv("CODIGO_CIUDAD", "LSN").upper()

# Primero van las funciones helpers de conexion a la db y al broker
def _get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def _get_rabbitmq_channel():
    credentials = pika.PlainCredentials(
        os.environ["RABBITMQ_USER"],
        os.environ["RABBITMQ_PASSWORD"],
    )
    ctx = ssl.create_default_context()
    ssl_opts = pika.SSLOptions(ctx)
    params = pika.ConnectionParameters(
        host=os.environ["RABBITMQ_HOST"],
        port=int(os.environ.get("RABBITMQ_PORT", 5671)),
        virtual_host="fulfillment",
        credentials=credentials,
        ssl_options=ssl_opts,
        heartbeat=60,
    )
    conn = pika.BlockingConnection(params)
    return conn, conn.channel()

# Verifica si la suscripcion debe continuar segun budget y cantidad en la db
def check_subscription(event, context):
   
    subscription_id = event["subscription_id"]

    conn = _get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT * FROM subscriptions WHERE id = %s", (subscription_id,))
        sub = cursor.fetchone()

        if not sub:
            print(f"[!] Suscripcion {subscription_id} no encontrada.")
            return {"subscription_id": subscription_id, "should_continue": False}

        should_continue = (
            sub["status"] == "active"
            and sub["packages_sent"] < sub["quantity"]
            and sub["budget_remaining"] >= sub["cost_per_shipment"]
        )

        # Actualizar estado final si corresponde
        if not should_continue and sub["status"] == "active":
            new_status = (
                "completed" if sub["packages_sent"] >= sub["quantity"] else "budget_exhausted"
            )
            cursor.execute(
                "UPDATE subscriptions SET status = %s, updated_at = %s WHERE id = %s",
                (new_status, datetime.now(timezone.utc), subscription_id),
            )
            conn.commit()
            print(f"[*] Suscripcion {subscription_id} finalizada con estado: {new_status}")

        return {
            "subscription_id": subscription_id,
            "should_continue": should_continue,
            "periodicity_seconds": sub["periodicity_seconds"],
            "destination_id": sub["destination_id"],
            "height": float(sub["height"]),
            "width": float(sub["width"]),
            "depth": float(sub["depth"]),
            "criteria": sub["criteria"],
            "max_hops": sub["max_hops"],
            "meta_content": sub["meta_content"] or "",
            "cost_per_shipment": float(sub["cost_per_shipment"]),
            "deliver_not_before": (
                sub["deliver_not_before"].isoformat() if sub["deliver_not_before"] else None
            ),
        }
    finally:
        cursor.close()
        conn.close()

# Crea, envia un paquete y actualiza la suscripcion
def execute_delivery(event, context):
    
    subscription_id = event["subscription_id"]
    destination_id = event["destination_id"]
    criteria = event["criteria"]
    max_hops = event["max_hops"]
    periodicity_seconds = event["periodicity_seconds"]
    meta_content = event.get("meta_content", "")
    cost_per_shipment = float(event.get("cost_per_shipment", 0))
    deliver_not_before_raw = event.get("deliver_not_before")

    conn = _get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Determinar el siguiente salto
        next_hop = _resolve_next_hop(cursor, destination_id, criteria)

        now = datetime.now(timezone.utc)
        pkg_id = str(uuid.uuid4())
        deliver_not_before = deliver_not_before_raw or now.isoformat()

        # Insertar paquete
        cursor.execute(
            """
            INSERT INTO packages (
                id, origin_id, destination_id, max_hops, created_at, deliver_not_before,
                meta_content, is_meta_encrypted, constraints, payment,
                status, last_action, last_processed_at, received_from, shipment_request_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, false, %s, %s,
                'forwarded', 'forwarded', %s, %s, null
            )
            """,
            (
                pkg_id,
                CODIGO_CIUDAD,
                destination_id,
                max_hops,
                now,
                deliver_not_before,
                meta_content,
                json.dumps({"criteria": criteria}),
                cost_per_shipment,
                now,
                CODIGO_CIUDAD,
            ),
        )

        # Registrar vinculo suscripcion-paquete
        cursor.execute(
            """
            INSERT INTO subscription_packages (id, subscription_id, package_id, status, created_at)
            VALUES (%s, %s, %s, 'sent', %s)
            """,
            (str(uuid.uuid4()), subscription_id, pkg_id, now),
        )

        # Actualizar contadores de la suscripcion
        cursor.execute(
            """
            UPDATE subscriptions
            SET packages_sent    = packages_sent + 1,
                budget_remaining = budget_remaining - %s,
                updated_at       = %s
            WHERE id = %s
            """,
            (cost_per_shipment, now, subscription_id),
        )

        conn.commit()

        # Publicar a RabbitMQ
        _publish_package(
            pkg_id=pkg_id,
            destination_id=destination_id,
            next_hop=next_hop,
            max_hops=max_hops,
            now=now,
            deliver_not_before=deliver_not_before,
            meta_content=meta_content,
            criteria=criteria,
            cost_per_shipment=cost_per_shipment,
        )

        # Evento de auditoria
        cursor.execute(
            """
            INSERT INTO package_events (id, package_id, event_type, timestamp, next_city_id)
            VALUES (%s, %s, 'forwarded', %s, %s)
            """,
            (str(uuid.uuid4()), pkg_id, now, next_hop),
        )
        conn.commit()

        print(f"[*] Paquete de suscripcion {pkg_id} enviado a {next_hop}")
        return {
            "subscription_id": subscription_id,
            "periodicity_seconds": periodicity_seconds,
            "package_id": pkg_id,
        }

    except Exception as exc:
        conn.rollback()

        # Marcar la entrada de subscription_package como fallida si existe
        try:
            cursor.execute(
                """
                UPDATE subscription_packages SET status = 'failed'
                WHERE subscription_id = %s AND package_id = %s
                """,
                (subscription_id, pkg_id if "pkg_id" in dir() else ""),
            )
            conn.commit()
        except Exception:
            pass
        print(f"[!] Error en execute_delivery: {exc}")
        raise
    finally:
        cursor.close()
        conn.close()

# Retorna el siguiente salto optimo hacia destination_id
def _resolve_next_hop(cursor, destination_id: str, criteria: str) -> str:
    # Primero intentar conexion directa
    cursor.execute(
        """
        SELECT destination_code FROM city_connections
        WHERE source_code = %s AND destination_code = %s AND enabled = true
        LIMIT 1
        """,
        (CODIGO_CIUDAD, destination_id),
    )
    row = cursor.fetchone()
    if row:
        return destination_id

    # Si no hay conexion directa, elegir el vecino con menor costo/distancia
    cost_field = "transport_cost" if criteria == "price" else "distance"
    cursor.execute(
        f"""
        SELECT destination_code FROM city_connections
        WHERE source_code = %s AND enabled = true
        ORDER BY {cost_field} ASC
        LIMIT 1
        """,
        (CODIGO_CIUDAD,),
    )
    row = cursor.fetchone()
    return row["destination_code"] if row else destination_id


def _publish_package(
    pkg_id: str,
    destination_id: str,
    next_hop: str,
    max_hops: int,
    now: datetime,
    deliver_not_before,
    meta_content: str,
    criteria: str,
    cost_per_shipment: float,
):

    deliver_str = (
        deliver_not_before
        if isinstance(deliver_not_before, str)
        else deliver_not_before.isoformat()
    )
    package_body = {
        "id": pkg_id,
        "originId": CODIGO_CIUDAD,
        "destinationId": destination_id,
        "maxHops": max_hops - 1,
        "createdAt": now.isoformat(),
        "deliverNotBefore": deliver_str,
        "metaContent": meta_content,
        "constraints": {"criteria": criteria},
        "payment": cost_per_shipment,
    }
    message = {
        "idpk": str(uuid.uuid4()),
        "msgId": str(uuid.uuid4()),
        "type": "package-transit",
        "timestamp": now.isoformat(),
        "cityId": CODIGO_CIUDAD,
        "packageBody": package_body,
    }
    try:
        rmq_conn, channel = _get_rabbitmq_channel()
        channel.basic_publish(
            exchange="fulfillment.x",
            routing_key=f"city.{next_hop.lower()}",
            body=json.dumps(message),
            mandatory=True,
        )
        rmq_conn.close()
    except Exception as e:
        print(f"[!] Error publicando paquete {pkg_id} en RabbitMQ: {e}")
