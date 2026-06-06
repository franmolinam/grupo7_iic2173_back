import os
import httpx
import time

JOBS_MASTER_URL = os.getenv("JOBS_MASTER_URL", "http://localhost:8001")
CODIGO_CIUDAD = os.getenv("CODIGO_CIUDAD", "LSN").upper()

POLL_ATTEMPTS = 15   # máximo de intentos
POLL_INTERVAL = 2    # segundos entre intentos

def get_routes(origin: str, destination: str, criteria: str) -> dict:
    # 1. Crear el job
    try:
        response = httpx.post(
            f"{JOBS_MASTER_URL}/job",
            json={"origin": origin, "destination": destination, "criteria": criteria},
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.TimeoutException:
        raise RuntimeError("JobsMaster no respondió al crear el job (timeout)")
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"JobsMaster rechazó el job: {e.response.status_code}")
    except Exception as e:
        raise RuntimeError(f"No se pudo conectar al JobsMaster: {e}")

    # 2. Extraer jobId
    try:
        job_id = response.json()["jobId"]
    except (KeyError, ValueError):
        raise RuntimeError("JobsMaster devolvió una respuesta malformada al crear el job")

    # 3. Polling hasta que el job esté listo
    for attempt in range(POLL_ATTEMPTS):
        time.sleep(POLL_INTERVAL)
        try:
            result = httpx.get(
                f"{JOBS_MASTER_URL}/job/{job_id}",
                timeout=10.0,
            )
            result.raise_for_status()
            data = result.json()
        except httpx.TimeoutException:
            print(f"[!] JobsMaster timeout en intento {attempt + 1}/{POLL_ATTEMPTS}")
            continue
        except Exception as e:
            print(f"[!] Error consultando job {job_id}: {e}")
            continue

        status = data.get("status")

        if status == "done":
            # Validar que la respuesta tiene los campos necesarios
            if "routeMetricCost" not in data or "hops" not in data or "hopCount" not in data:
                raise RuntimeError("JobsMaster devolvió 'done' pero con respuesta malformada")
            return data

        elif status == "failed":
            raise RuntimeError(f"El JobsMaster falló al calcular la ruta: {data.get('error', 'sin detalle')}")

        # status == "pending" → seguir esperando
        print(f"[*] Job {job_id} aún pendiente (intento {attempt + 1}/{POLL_ATTEMPTS})")

    raise RuntimeError(
        f"JobsMaster no completó el job {job_id} tras {POLL_ATTEMPTS * POLL_INTERVAL}s"
    )

# Para verificar si el JobsMaster está operativo
def check_heartbeat() -> bool:
    try:
        response = httpx.get(f"{JOBS_MASTER_URL}/heartbeat", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False