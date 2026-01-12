from uuid import uuid4

from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    DateTime,
    String,
    Text,
    Numeric,
    func
)

from database import Database


class TariffPlan(Database.Base):
    __tablename__ = "tariff_plans"

    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid4,
        comment="Уникальный идентификатор"
    )	
    code = Column(
        String(50),
        unique=True,
        nullable=False,
        comment="Код тарифа: 'demo', 'starter', 'pro', 'enterprise'"
    )
    name = Column(
        String(255),
        nullable=False,
        comment="Отображаемое название: 'Демо', 'Старт (для ИП)', 'Про', 'Бизнес'"
    )
    description = Column(
        Text,
        comment='Описание для лендинга: "7 дней бесплатно, без карты"'
    )
    price_rub = Column(
        Numeric(10, 2),
        nullable=False,
        default=0.00,
        comment="Цена в рублях за месяц (0.00 для демо)"
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Активен ли тариф (можно скрыть без удаления)"
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Когда создан"
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Последнее изменение цены/лимитов"
    )

    def __repr__(self):
        return (
            f"<TariffPlan("
            f"id={self.id}, "
            f"code={self.code}, "
            f"name={self.name}")