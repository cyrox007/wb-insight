from datetime import date, datetime
from typing import Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Database

class WbRealizationReport(Database.Base):
    __tablename__ = 'wb_realization_reports'

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

    # ========== Ключевые даты (из официального ответа API) ==========

    # Дата отчёта (ключевое поле для агрегации по дням!)
    rr_dt: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True
    )

    # Дата заказа
    order_dt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Дата продажи
    sale_dt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Период отчёта
    date_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Дата создания отчёта
    create_dt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # ========== Идентификаторы ==========

    # Артикул WB товара (nmID)
    nm_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )

    # ID строки отчёта (уникальный идентификатор записи)
    rrd_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
        index=True
    )

    # Номер поставки
    gi_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )

    # Штрих-код (shkId)
    shk_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )

    # Уникальный идентификатор заказа
    srid: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        index=True
    )

    # Номер отчета
    realization_report_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )

    # ========== Типы операций и документов ==========

    # Тип операции: "Продажа", "Возврат", "Логистика" и т.д.
    supplier_oper_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )

    # Тип документа
    doc_type_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )

    # ========== Товарные данные ==========

    # Предмет
    subject_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )

    # Бренд
    brand_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        index=True
    )

    # Артикул продавца
    sa_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )

    # Размер
    ts_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )

    # Баркод
    barcode: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        index=True
    )

    # Название товара (новое поле в API)
    title: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )

    # Склад
    office_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )

    # Тип коробов
    gi_box_type_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )

    # Номер офиса доставки
    ppvz_office_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )

    # Наименование офиса доставки
    ppvz_office_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )

    # ========== Финансовые данные ==========

    # Количество единиц
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    # Цена розничная
    retail_price: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True
    )

    # Сумма продажи/возврата
    retail_amount: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=False
    )

    # Цена с учетом скидки
    retail_price_with_disc_rub: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True
    )

    # Согласованная скидка (%)
    sale_percent: Mapped[float] = mapped_column(
        Numeric(10, 4),
        default=0,
        nullable=True
    )

    # Процент комиссии
    commission_percent: Mapped[float] = mapped_column(
        Numeric(10, 4),
        default=0,
        nullable=True
    )

    # Продуктовый дисконт
    product_discount_for_report: Mapped[float] = mapped_column(
        Numeric(10, 4),
        default=0,
        nullable=True
    )

    # Скидка постоянного покупателя
    ppvz_spp_prc: Mapped[float] = mapped_column(
        Numeric(10, 4),
        default=0,
        nullable=True
    )

    # ========== KVV (комиссия за выдачу и возврат) ==========

    # Размер КВВ без НДС
    ppvz_kvw_prc_base: Mapped[float] = mapped_column(
        Numeric(10, 4),
        default=0,
        nullable=True
    )

    # Итоговый КВВ без НДС
    ppvz_kvw_prc: Mapped[float] = mapped_column(
        Numeric(10, 4),
        default=0,
        nullable=True
    )

    # Снижение КВВ из-за рейтинга
    sup_rating_prc_up: Mapped[float] = mapped_column(
        Numeric(10, 4),
        default=0,
        nullable=True
    )

    # Снижение КВВ из-за акции
    is_kgvp_v2: Mapped[float] = mapped_column(
        Numeric(10, 4),
        default=0,
        nullable=True
    )

    # Комиссия маркетплейса
    ppvz_sales_commission: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=False
    )

    # К перечислению
    ppvz_for_pay: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=False
    )

    # Возмещение за выдачу и возврат товаров
    ppvz_reward: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True
    )

    # Вознаграждение WB без НДС
    ppvz_vw: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True
    )

    # НДС с вознаграждения WB
    ppvz_vw_nds: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True
    )

    # ========== Логистика ==========

    # Стоимость доставки
    delivery_rub: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=False
    )

    # Стоимость возврата
    return_rub: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True
    )

    # Количество доставок
    delivery_amount: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=True
    )

    # Количество возвратов
    return_amount: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=True
    )

    # Возмещение издержек по перевозке
    rebill_logistic_cost: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True
    )

    # Организатор перевозки
    rebill_logistic_org: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )

    # Стоимость хранения
    storage_fee: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True
    )

    # Стоимость платной приемки
    acceptance: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True
    )

    # ========== Платежи и штрафы ==========

    # Штрафы
    penalty: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True
    )

    # Доплаты
    additional_payment: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True
    )

    # Прочие удержания
    deduction: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True
    )

    # Издержки по эквайрингу
    acquiring_fee: Mapped[float] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True
    )

    # Банк эквайер
    acquiring_bank: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )

    # ========== Промо и маркетинг ==========

    # Промокод
    supplier_promo: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )

    # Уникальный идентификатор заказа
    order_uid: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )

    # Код маркировки
    kiz: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )

    # Номер таможенной декларации
    declaration_number: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )

    # ========== Информация о партнере ==========

    # Номер партнера (больше не поддерживается в новом API!)
    ppvz_supplier_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )

    # Партнер
    ppvz_supplier_name: Mapped[Optional[str]] = mapped_column(
        String(300),
        nullable=True
    )

    # ИНН партнера
    ppvz_inn: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True
    )

    # ========== Мета отчета ==========

    # Валюта отчета
    currency_name: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )

    # Тип отчета
    report_type: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )

    # Месяц
    trbx_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )

    # ========== Для аудита ==========

    # Дата создания записи в БД
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False
    )

    __table_args__ = (
        # Индекс для быстрого поиска по периоду и пользователю
        Index('idx_wb_realization_user_rrdt', 'user_id', 'rr_dt'),

        # Индекс для поиска по артикулу и дате
        Index('idx_wb_realization_user_nm_rrdt', 'user_id', 'nm_id', 'rr_dt'),

        # Индекс для поиска по бренду
        Index('idx_wb_realization_brand', 'brand_name'),

        # Индекс для поиска по баркоду
        Index('idx_wb_realization_barcode', 'barcode'),
    )

    def __repr__(self):
        return (
            f"<WbRealizationReport("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"rr_dt={self.rr_dt}, "
            f"nm_id={self.nm_id}, "
            f"type={self.supplier_oper_name}, "
            f"amount={self.retail_amount}"
            f")>"
        )