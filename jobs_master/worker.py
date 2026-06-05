import json
import os
import psycopg2
import heapq

def get_db_connection():
    return psycopg2.connect(os.environ['DATABASE_URL'])

def calculate_route(event, context):
    job_id = event.get("jobId")
    origen = event.get("origin")
    destino = event.get("destination")
    criterio = event.get("criteria")
    
    print(f"[*] Calculando ruta {origen} -> {destino} (Criterio: {criterio})")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Primero se obtienen todas las rutas de la tabla
        cursor.execute("SELECT source_code, destination_code, destination_name, distance, transport_cost, enabled FROM city_connections")
        conexiones = cursor.fetchall()
        
        # Ahora se construye el grafo
        grafo = {}
        for src, dst, name, dist, cost, enabled in conexiones:
            if not enabled:
                continue # Si la ciudad no responde o esta deshabilitada se ignora
                
            if src not in grafo:
                grafo[src] = {}
            
            peso = cost if criterio == "price" else dist
            grafo[src][dst] = peso

        # Algoritmo de Dijkstra
        distancias_minimas = {nodo: float('inf') for nodo in grafo.keys()}
        distancias_minimas[origen] = 0
        
        cola_prioridad = [(0, origen, [origen])]
        
        ruta_final = []
        costo_final = 0
        
        # Si el origen no está en el grafo, es inalcanzable
        if origen in grafo:
            while cola_prioridad:
                costo_actual, ciudad_actual, camino = heapq.heappop(cola_prioridad)
                
                # Se termina si se llega al destino
                if ciudad_actual == destino:
                    ruta_final = camino
                    costo_final = costo_actual
                    break
                    
                # Se ignora si se encuentra un costo mayor al registrado
                if costo_actual > distancias_minimas.get(ciudad_actual, float('inf')):
                    continue
                    
                # Se revisan los vecinos
                for vecino, peso in grafo.get(ciudad_actual, {}).items():
                    nuevo_costo = costo_actual + peso
                    
                    if nuevo_costo < distancias_minimas.get(vecino, float('inf')):
                        distancias_minimas[vecino] = nuevo_costo
                        heapq.heappush(cola_prioridad, (nuevo_costo, vecino, camino + [vecino]))

        # Se guardan los resultados en la db
        status = "done" if ruta_final else "failed"
        hop_count = len(ruta_final) - 1 if ruta_final else 0
        
        cursor.execute(
            """
            UPDATE routing_jobs 
            SET status = %s, route_metric_cost = %s, hops = %s, hop_count = %s
            WHERE id = %s
            """,
            (status, costo_final, json.dumps(ruta_final), hop_count, job_id)
        )
        conn.commit()
        print(f"[*] Job {job_id} finalizado con estado: {status}")

    except Exception as e:
        print(f"[!] Error en worker: {e}")
        conn.rollback()
        cursor.execute("UPDATE routing_jobs SET status = 'failed' WHERE id = %s", (job_id,))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
        
    return {"status": "success"}