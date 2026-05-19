from typing import Optional
from sqlalchemy import String, Text, Numeric, DateTime
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy import ForeignKey
from decimal import Decimal

from datetime import datetime

from src.db.base import Base

class Procurement(Base):

    __tablename__ = "procurement"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    procuring_entity_id: Mapped[int] = mapped_column(ForeignKey("procuring_entity.id"))
    pncp_control_number: Mapped[str] = mapped_column(String(50), nullable=False)
    procurement_object: Mapped[str] = mapped_column(Text, nullable=False)
    additional_information: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=18, scale=2),
        nullable=True
    )

    tender_start_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tender_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"Procurement(id={self.id!r}, procuring_entity_id={self.procuring_entity_id!r}, estimated_price={self.estimated_price!r})"