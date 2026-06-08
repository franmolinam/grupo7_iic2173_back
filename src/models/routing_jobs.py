from sqlalchemy import Column, String, Float, Integer, JSON
from src.database import Base

class RoutingJob(Base):
    __tablename__ = "routing_jobs"

    id = Column(String, primary_key=True)
    status = Column(String, nullable=False, default="pending")
    criteria = Column(String, nullable=False)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    route_metric_cost = Column(Float, nullable=True)
    hops = Column(JSON, nullable=True) # Para guardar el arreglo de saltos
    hop_count = Column(Integer, nullable=True)