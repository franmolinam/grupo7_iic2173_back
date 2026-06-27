import os
from src.services.jobs_master_service import get_routes

MAX_LINEAR_CM = 3000
MIN_PRICE = 5000
MAX_PRICE = 100_000

CODIGO_CIUDAD = os.getenv("CODIGO_CIUDAD", "LSN").upper()


def validate_dimensions(height: float, width: float, depth: float) -> None:
    total = height + width + depth
    if total > MAX_LINEAR_CM:
        raise ValueError(
            f"Las dimensiones superan el máximo de {MAX_LINEAR_CM} cm lineales. "
            f"Total: {total:.1f} cm"
        )


def calculate_price(h: float, w: float, d: float, route_metric_cost: float, fprice: float, insured: bool = False) -> int:
    raw = 0.01 * (h + w + d) * route_metric_cost * fprice
    base = int(max(MIN_PRICE, min(MAX_PRICE, raw)))
    if insured:
        base = int(base * 1.05)
    return base


def get_quotation(
    destination_id: str,
    height: float,
    width: float,
    depth: float,
    criteria: str,
    max_hops: int,
    fprice: float,
    insured: bool = False,
) -> dict:
    # 1. Validar dimensiones
    validate_dimensions(height, width, depth)

    # 2. Consultar JobsMaster
    destination_upper = destination_id.upper()
    route = get_routes(CODIGO_CIUDAD, destination_upper, criteria)

    # 3. Validar alcanzabilidad,
    # si hopCount es 0 o hops está vacío, no es alcanzable
    if not route.get("hops") or route.get("hopCount", 0) == 0:
        raise ValueError(
            f"La ciudad destino '{destination_id}' no es alcanzable desde esta sucursal"
        )

    # 4. Validar que maxHops sea suficiente
    hops_count = route["hopCount"]
    if max_hops < hops_count:
        raise ValueError(
            f"maxHops insuficiente: la ruta óptima requiere {hops_count} saltos "
            f"pero se indicaron {max_hops}"
        )

    # 5. Calcular precio
    route_metric_cost = route["routeMetricCost"]
    final_price = calculate_price(height, width, depth, route_metric_cost, fprice, insured)
    insurance_premium = int(final_price - int(final_price / 1.05)) if insured else 0

    # El siguiente salto es el segundo elemento del array hops
    next_hop = route["hops"][1] if len(route["hops"]) > 1 else destination_upper

    return {
        "criteria": criteria,
        "route_metric_cost": route_metric_cost,
        "hops_count": hops_count,
        "next_hop": next_hop,
        "full_path": route["hops"],
        "fprice": fprice,
        "final_price": final_price,
        "insurance_premium": insurance_premium,
    }