import json
import uuid
import boto3
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Cliente de AWS Lambda
lambda_client = boto3.client('lambda')

# Función auxiliar para conectar a la DB
def get_db_connection():
    return psycopg2.connect(os.environ['DATABASE_URL'])

# Endpoint GET/heartbeat
def heartbeat(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "ok", 
            "alive": True
        })
    }

# Endpoint para crear un nuevo job de calculo de ruta
# POST/job
def create_job(event, context):
    try:
        # Primero se extrae el payload de la peticion
        body = json.loads(event.get("body", "{}"))
        origen = body.get("origin")
        destino = body.get("destination")
        criterio = body.get("criteria")

        # Se genera in id para el trabajo
        job_id = str(uuid.uuid4())

        # Se debe guardar en la db el estado pending
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO routing_jobs (id, status, criteria, origin, destination) 
            VALUES (%s, %s, %s, %s, %s)
            """,
            (job_id, 'pending', criterio, origen, destino)
        )
        conn.commit()
        cursor.close()
        conn.close()

        # Se prepara el payload para el worker
        worker_payload = {
            "jobId": job_id,
            "origin": origen,
            "destination": destino,
            "criteria": criterio
        }
        
        # Ahora se invoca el worker de forma asincrona        
        lambda_client.invoke(
            FunctionName= os.environ['WORKER_FUNCTION_NAME'],
            InvocationType='Event', # Esto marca que sea asincrono
            Payload=json.dumps(worker_payload)
        )
        
        return {
            "statusCode": 201,
            "body": json.dumps({"jobId": job_id, "status": "pending"})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

# Endpoint para consultar estado
# GET/job/{id}
def get_job(event, context):
    try:
        # Primero se extrae el id de la URL
        job_id = event["pathParameters"]["id"]
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor) # Con RealDictCursor se obtiene un diccionario en vez de una tupla
        cursor.execute("SELECT * FROM routing_jobs WHERE id = %s", (job_id,))
        job = cursor.fetchone()
        cursor.close()
        conn.close()

        if not job:
            return {"statusCode": 404, "body": json.dumps({"error": "Job not found"})}
        
        # Se construye la respuesta con el estado actual del job
        response = {
            "jobId": job["id"],
            "status": job["status"]
        }

        if job["status"] == "done":
            response.update({
                "routeMetricCost": job["route_metric_cost"],
                "hops": job["hops"],
                "hopCount": job["hop_count"]
            })

        return {
            "statusCode": 200,
            "body": json.dumps(response)
        }
    
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }