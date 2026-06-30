import time
import functools

#  Este decorador es aplicable a cualquier funcion para que se reintente
# la ejecucion utilizando un delay basado en la secuencia de Fibonacci
def fibonacci_retry(max_retries=6): # Se eligio un maximo de 6 reintentos para evitar loops infinitos o muy largos
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Primero se debe iniciar la secuencia de Fibonacci
            a, b = 1, 1
            retries = 0
            
            while retries < max_retries:
                try:
                    # Se intenta ejecutar la funcion original
                    return func(*args, **kwargs)
                
                except Exception as e:
                    retries += 1 # Cada fallo suma un reintento
                    if retries >= max_retries:
                        print(f"[!] Fallo definitivo en {func.__name__} despues de {max_retries} intentos. Error: {e}")
                        raise e # Si ya no quedan reintentos se lanza el error
                    
                    print(f"[!] Error en peticion al broker: {e}.")
                    print(f"[*] Reintentando en {a} segundos (Intento {retries} / {max_retries - 1})...")
                    
                    time.sleep(a)
                    
                    # En esta parte se avanza en la secuencia de Fibonacci para el siguiente delay
                    a, b = b, a + b
                    
        return wrapper
    return decorator