from sqlalchemy import Column, ForeignKey, String, Integer, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from src.database import Base

# modelo de paquete
class Package(Base):
    __tablename__ = "packages"

    # campos que trae el paquete
    id = Column(String, primary_key=True)
    origin_id = Column(String, nullable=False)
    destination_id = Column(String, nullable=False)
    max_hops = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)
    deliver_not_before = Column(DateTime, nullable=False)
    meta_content = Column(String, nullable=True)
    is_meta_encrypted = Column(Boolean, default=False)
    priority_class = Column(String, nullable=True)
    payment = Column(Integer, nullable=True)
    constraints = Column(JSON, nullable=True)
    delivery_strategy = Column(String, nullable=True)
    shipment_request_id = Column(String, ForeignKey("shipment_requests.id"), nullable=True)

    # para q sea seguro 
    is_insured = Column(Boolean, default=False)
    insurance_premium = Column(Integer, nullable=True)

    # campos que tengo que sumar para el seguimiento
    # Estado actual del paquete en nuestra ciudad
    status = Column(String, nullable=False, default="received")
    # última acción realizada sobre el paquete
    last_action = Column(String, nullable=True)
    # cuándo fue la última vez que procesamos este paquete
    last_processed_at = Column(DateTime, nullable=True)
    # desde qué ciudad nos llegó
    received_from = Column(String, nullable=True)

    # relación con eventos del paquete
    events = relationship("PackageEvent", back_populates="package")
    shipment_request = relationship("ShipmentRequest", back_populates="package")

    def __repr__(self):
        return f"<Package id={self.id} status={self.status}>"