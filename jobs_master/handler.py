import json
import uuid

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
        
        # TO DO (Paso 3): Aquí guardaremos en base de datos el estado "pending" 
        # y lanzaremos el worker asíncrono para que calcule la ruta.
        
        print(f"Job {job_id} creado para buscar ruta {origen} -> {destino} por {criterio}")
        
        return {
            "statusCode": 201,
            "body": json.dumps({
                "jobId": job_id,
                "status": "pending"
            })
        }
    except Exception as e:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": str(e)})
        }

# Endpoint para consultar estado
# GET/job/{id}
def get_job(event, context):
    # Primero se extrae el id de la URL
    job_id = event["pathParameters"]["id"]
    
    # TO DO (Paso 3): Aquí consultaremos la base de datos para ver si el worker
    # ya terminó de calcular la ruta de este job_id.
    
    # Por ahora, devolvemos el mock exacto que Back 2 te pidió:
    mock_response = {
        "jobId": job_id,
        "status": "done",
        "routeMetricCost": 12000,
        "hops": ["COR", "TRA", "HGW"],
        "hopCount": 2
    }
    
    return {
        "statusCode": 200,
        "body": json.dumps(mock_response)
    }