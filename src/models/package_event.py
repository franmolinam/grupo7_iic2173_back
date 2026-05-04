from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from src.database import Base

# evento del paquete
class PackageEvent(Base):
    __tablename__ = "package_events"

    # campos del evento del paquete
    id = Column(String, primary_key=True)
    package_id = Column(String, ForeignKey("packages.id"), nullable=False)
    # tipo de evento (received, processed, sent, delivered, transit, redirected)
    event_type = Column(String, nullable=False) 
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # para transit y redirected
    next_city_id = Column(String, nullable=True)
    # para saber desde donde llegó
    from_city_id = Column(String, nullable=True) 

    # relación con paquete
    package = relationship("Package", back_populates="events")

    # debugging
    def __repr__(self):
        return f"<PackageEvent pkg={self.package_id} type={self.event_type}>"