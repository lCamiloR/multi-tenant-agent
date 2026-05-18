from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy import ForeignKey

from src.db.base import Base

class Procurement(Base):

    __tablename__ = "procurement"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    procuring_entity_id: Mapped[int] = mapped_column(ForeignKey("procuring_entity.id"))
    pncp_control_number: Mapped[str] = mapped_column(String(30), nullable=False)
    procurement_object: Mapped[str] = mapped_column(String(300))
    additional_information: Mapped[str] = mapped_column(String(300))
    estimated_price: Mapped[float] = mapped_column()

    def __repr__(self) -> str:
        return f"Procurement(id={self.id!r}, procuring_entity_id={self.procuring_entity_id!r}, estimated_price={self.estimated_price!r})"