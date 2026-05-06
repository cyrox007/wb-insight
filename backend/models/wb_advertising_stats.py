from datetime import date, datetime
from typing import Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database


class WbAdvertisingStats(Database.Base):
    """
    Модель для хранения статистики по рекламным кампаниям Wildberries
    
    API Wildberries (advert-api.wildberries.ru):
    ===========================================
    - GET /api/advert/v2/adverts - список кампаний
      Документация: https://dev.wildberries.ru/docs/openapi/promotion/#tag/Kampanii/paths/~1api~1advert~1v2~1adverts/get
      
    - GET /adv/v3/fullstats - полная статистика по кампаниям
      Документация: https://dev.wildberries.ru/docs/openapi/promotion/#tag/Statistika/paths/~1adv~1v3~1fullstats/get
    
    Соответствие полей БД, API Wildberries и Excel:
    =====================================================================================================
    | Поле БД              | Поле API WB (camelCase)   | Колонка Excel       | Описание                  |
    |----------------------|---------------------------|---------------------|---------------------------|
    | campaign_id          | advertId                  | ID кампании         | ID рекламной кампании     |
    | date                 | date                      | Дата                | Дата статистики           |
    | platform_type        | platformType              | Тип Платформы       | Тип платформы (32, 64)    |
    | product_name         | productName               | Имя товара          | Название товара           |
    | nm_id                | nmId                      | nmId                | Артикул WB                |
    | views                | views                     | Просмотры           | Количество просмотров     |
    | clicks               | clicks                    | Клики               | Количество кликов         |
    | ctr                  | ctr                       | CTR                 | CTR (%)                   |
    | cpc                  | cpc                       | CPC                 | Цена за клик (₽)          |
    | amount               | sum                       | Сумма               | Затраты на рекламу (₽)    |
    | added_to_cart        | atbs                      | Добавлено в корзину | Добавления в корзину, шт. |
    | orders               | orders                    | Заказы              | Количество заказов        |
    | cr                   | cr                        | CR                  | Конверсия (%)             |
    | shks                 | shks                      | SHKS                | Заказано товаров, шт.     |
    | orders_amount        | sum_price                 | Сумма заказов       | Сумма заказов (₽)         |
    | avg_position         | boosterStats[].avgPosition| avg_position        | Средняя позиция показа    |
    | company              | companyName               | Компания            | Название компании         |
    =====================================================================================================
    
    Пример ответа API /adv/v3/fullstats:
    [
      {
        "advertId": 22161678,
        "views": 1000,
        "clicks": 50,
        "ctr": 5.0,
        "cpc": 1.5,
        "sum": 75.0,
        "atbs": 10,
        "orders": 5,
        "cr": 10.0,
        "shks": 5,
        "sum_price": 15000.0,
        "days": [
          {
            "date": "2025-07-06",
            "views": 100,
            "clicks": 5,
            ...
          }
        ],
        "boosterStats": [{"avgPosition": 75.0}]
      }
    ]
    """
    __tablename__ = 'wb_advertising_stats'

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    # Привязка к пользователю
    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # привязка к токену
    token_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey('api_tokens.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # ========== Идентификаторы кампании и товара ==========
    # ID рекламной кампании (advertId в API WB)
    campaign_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )

    # Артикул WB товара (nmID в API WB)
    nm_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )

    # ========== Даты ==========
    # Дата статистики
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True
    )

    # Дата создания записи в БД
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False
    )

    # ========== Платформа и товар ==========
    # Тип платформы (platformType в API WB, значения: 32, 64 и т.д.)
    platform_type: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )

    # Имя товара (productName в API WB)
    product_name: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Компания (companyName в API WB)
    company: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )

    # ========== Метрики просмотров и кликов ==========
    # Просмотры (views в API WB)
    views: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    # Клики (clicks в API WB)
    clicks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    # CTR (Click-Through Rate) - процент кликабельности (ctr в API WB)
    ctr: Mapped[float] = mapped_column(
        Numeric(10, 4),
        default=0,
        nullable=True
    )

    # CPC (Cost Per Click) - цена за клик (cpc в API WB)
    cpc: Mapped[float] = mapped_column(
        Numeric(10, 4),
        default=0,
        nullable=True
    )

    # Сумма расходов на рекламу (sum в API WB)
    amount: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=False
    )

    # ========== Метрики конверсий ==========
    # Добавлено в корзину (atbs в API WB)
    added_to_cart: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    # Заказы (orders в API WB)
    orders: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    # CR (Conversion Rate) - процент конверсии (cr в API WB)
    cr: Mapped[float] = mapped_column(
        Numeric(10, 4),
        default=0,
        nullable=True
    )

    # SHKS - количество штук в заказах (shks в API WB)
    shks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    # Сумма заказов (sum_price в API WB)
    orders_amount: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=False
    )

    # ========== Позиции ==========
    # Средняя позиция показа (из boosterStats в API WB)
    avg_position: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        default=0,
        nullable=True
    )

    __table_args__ = (
        # Индекс для быстрого поиска по пользователю и дате
        Index('idx_wb_adv_user_date', 'user_id', 'date'),
        
        # Индекс для поиска по кампании и дате
        Index('idx_wb_adv_campaign_date', 'campaign_id', 'date'),
        
        # Индекс для поиска по артикулу и дате
        Index('idx_wb_adv_user_nm_date', 'user_id', 'nm_id', 'date'),
        
        # Уникальный индекс для предотвращения дублей
        Index('idx_wb_adv_unique', 'user_id', 'campaign_id', 'nm_id', 'date', 'platform_type', unique=True),
    )

    def __repr__(self):
        return (
            f"<WbAdvertisingStats("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"campaign_id={self.campaign_id}, "
            f"date={self.date}, "
            f"nm_id={self.nm_id}, "
            f"views={self.views}, "
            f"clicks={self.clicks}, "
            f"amount={self.amount}"
            f")>"
        )
