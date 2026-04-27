from sqlalchemy import Column, String, Boolean, Float
from src.database import Base

class CityConnection(Base):
    __tablename__ = "city_connections"

    destination_code = Column(String, primary_key=True)
    destination_name = Column(String, nullable=False)
    distance = Column(Float, nullable=True)
    transport_cost = Column(Float, nullable=True)
    enabled = Column(Boolean, default=False)

    def __repr__(self):
        return f"<CityConnection dest={self.destination_code} enabled={self.enabled}>"