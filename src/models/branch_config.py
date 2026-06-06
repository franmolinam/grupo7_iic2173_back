from sqlalchemy import Column, String, Float
from src.database import Base


class BranchConfig(Base):
    __tablename__ = "branch_config"

    key = Column(String, primary_key=True)
    value = Column(Float, nullable=False)

    def __repr__(self):
        return f"<BranchConfig {self.key}={self.value}>"