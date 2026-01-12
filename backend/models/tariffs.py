from uuid import uuid4

from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
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
    

class TariffLimit(Database.Base):
    __tablename__ = "tariff_limits"

    tariff_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tariff_plans.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Ссылка на тариф"
    )
    limit_type = Column(
        String(50),
        primary_key=True,
        comment="Тип лимита: 'wb_accounts', 'nm_ids', 'sync_frequency_hours', 'ai_queries_per_month', 'retention_days'"
    )
    limit_value = Column(
        Integer,
        nullable=False,
        comment="Числовое значение лимита"
    )

    def __repr__(self):
        return f"TariffLimit<{self.tariff_id}>"