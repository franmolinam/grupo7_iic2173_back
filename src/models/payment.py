from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from src.database import Base


# La aplicación debe persistir pagos
class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True)
    shipment_request_id = Column(String, ForeignKey("shipment_requests.id"), nullable=False)
    # para q cada usuario vea sus pagos:
    user_id = Column(String, nullable=False)

    # la aplicación debe validar la transacción mediante Webpay
    webpay_token = Column(String, nullable=True, unique=True) #idempotencia
    authorization_code = Column(String, nullable=True)
    # "TRYING" , "SUCCESS" o "FAILED"
    status = Column(String, nullable=False, default="TRYING")

    # debe manejar pago aprobado, rechazado y anulado 
    # y el mensaje de auditoría requiere paymentId, amount, currency
    amount = Column(Integer, nullable=False)        # en CLP
    currency = Column(String, nullable=False, default="CLP")

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=True) # para la auditoría, se actualiza cada vez que cambia el estado del pago

    shipment_request = relationship("ShipmentRequest", back_populates="payments")

    def __repr__(self):
        return f"<Payment id={self.id} status={self.status} amount={self.amount}>"