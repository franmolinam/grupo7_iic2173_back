from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from src.database import Base

class PackageEvent(Base):
    __tablename__ = "package_events"

    id = Column(String, primary_key=True)  # uuid del evento
    package_id = Column(String, ForeignKey("packages.id"), nullable=False)
    event_type = Column(String, nullable=False)  # received, transit, redirected, expired, delivered
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    next_city_id = Column(String, nullable=True)  # para transit y redirected
    from_city_id = Column(String, nullable=True)  # desde donde llegó

    # relación con paquete
    package = relationship("Package", back_populates="events")

    def __repr__(self):
        return f"<PackageEvent pkg={self.package_id} type={self.event_type}>"