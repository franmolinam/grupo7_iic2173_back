from sqlalchemy import Column, String, Integer, Float, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from src.database import Base

# La aplicación debe permitir que un usuario autenticado cree una solicitud de envío
# Solicitud de envío:
class ShipmentRequest(Base):
    __tablename__ = "shipment_requests"

    id = Column(String, primary_key=True)
    # para q cada usuario vea sus envíos:
    user_id = Column(String, nullable=False)
    origin_id = Column(String, nullable=False)
    destination_id = Column(String, nullable=False)

    # debe validar dimensiones (máx 3000 cm lineales)
    height = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    depth = Column(Float, nullable=False)

    # criterio por "price" o "distance"
    criteria = Column(String, nullable=False)
    max_hops = Column(Integer, nullable=False)
    deliver_not_before = Column(DateTime, nullable=True)
    meta_content = Column(String, nullable=True)

    # aplicación debe debe calcular y mostrar una cotización
    # incluyendo criterio usado, routeMetricCost, cantidad de saltos, siguiente salto o ruta, f_price y precio final
    # Resultado de la cotización (se llena al consultar el JobsMaster):
    route_metric_cost = Column(Float, nullable=True)
    hops_count = Column(Integer, nullable=True)
    next_hop = Column(String, nullable=True)
    full_path = Column(JSON, nullable=True) # ["LSN", "TRA", "HGW"]
    fprice = Column(Float, nullable=False, default=1.0)
    final_price = Column(Integer, nullable=True) # en CLP

    # necesito saber en qué estado está la solicitud antes/durante/después del pago
    # "pending_quote" -> "quoted" -> "paying" -> "paid" -> "failed" (para revisar el flujo)
    status = Column(String, nullable=False, default="pending_quote")

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    payments = relationship("Payment", back_populates="shipment_request")
    package = relationship("Package", back_populates="shipment_request", uselist=False)

    def __repr__(self):
        return f"<ShipmentRequest id={self.id} status={self.status}>"