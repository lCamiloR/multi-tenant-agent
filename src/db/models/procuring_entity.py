from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.db.base import Base

class ProcuringEntity(Base):

    __tablename__ = "procuring_entity"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    ibge_code: Mapped[int] = mapped_column(nullable=False)
    state_name: Mapped[str] = mapped_column(String(256), nullable=False)
    state_acronym: Mapped[str] = mapped_column(String(2), nullable=False)
    unit_code: Mapped[int] = mapped_column(nullable=False)
    unit_name: Mapped[str] = mapped_column(String(256), nullable=False)
    municipality_name: Mapped[str] = mapped_column(String(256), nullable=False)
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False, unique=True, index=True)

    def __repr__(self) -> str:
        return f"Procurement(id={self.id!r}, ibge_code={self.ibge_code!r}, unit_name={self.unit_name!r})"