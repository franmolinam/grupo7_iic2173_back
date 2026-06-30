from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from src.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)

    # Parametros del paquete que se repiten en cada entrega
    destination_id = Column(String, nullable=False)
    height = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    depth = Column(Float, nullable=False)
    criteria = Column(String, nullable=False)   # Price o distance
    max_hops = Column(Integer, nullable=False)
    deliver_not_before = Column(DateTime, nullable=True)
    meta_content = Column(String, nullable=True)

    # Configuración de la suscripcion
    periodicity_seconds = Column(Integer, nullable=False)  # 1 min a 2 dias
    budget = Column(Float, nullable=False)             # Prepago
    cost_per_shipment = Column(Float, nullable=False)  # Costo por cada envio
    quantity = Column(Integer, nullable=False)          # Max 100

    # Seguimiento
    packages_sent = Column(Integer, nullable=False, default=0)
    budget_remaining = Column(Float, nullable=False)
    # "active", "completed" (cantidad alcanzada), "budget_exhausted", "failed"
    status = Column(String, nullable=False, default="active")

    # ARN de la ejecucion de step functions
    execution_arn = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    subscription_packages = relationship("SubscriptionPackage", back_populates="subscription")

    def __repr__(self):
        return f"<Subscription id={self.id} status={self.status}>"


class SubscriptionPackage(Base):
    __tablename__ = "subscription_packages"

    id = Column(String, primary_key=True)
    subscription_id = Column(String, ForeignKey("subscriptions.id"), nullable=False)
    package_id = Column(String, ForeignKey("packages.id"), nullable=True)
    status = Column(String, nullable=False, default="sent")  # Sent o failed
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    subscription = relationship("Subscription", back_populates="subscription_packages")
    package = relationship("Package")

    def __repr__(self):
        return f"<SubscriptionPackage sub={self.subscription_id} pkg={self.package_id}>"
