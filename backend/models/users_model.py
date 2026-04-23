from datetime import datetime
from enum import Enum
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import UUID as PG_UUID, Boolean, DateTime, Float, String, Text, Index, Integer, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Database

if TYPE_CHECKING:
    from models.tokens_model import APIToken
    from models.user_sync_state_model import UserSyncState
    from models.subscription_model import Subscription


class EntityType(Enum):
    """
    Тип сущности пользователя.
    
    Attributes:
        INDIVIDUAL: Физическое лицо
        SELF_EMPLOYED: Самозанятый
        LEGAL_ENTITY: Юрлицо
    """
    INDIVIDUAL = "individual"
    SELF_EMPLOYED = "self_employed"
    LEGAL_ENTITY = "legal_entity"


class UserRole(Enum):
    """
    Роли пользователя в системе.
    
    Attributes:
        SUPER_ADMIN: Суперадмин
        ADMIN: Администратор
        MANAGER: Менеджер
        SUPPORT: Поддержка
        ANALYST: Аналитик
        USER: Обычный пользователь
    """
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    SUPPORT = "support"
    ANALYST = "analyst"
    USER = "user"


class UserRoleAssociation(Database.Base):
    """
    Связь многие-ко-многим между пользователями и ролями.
    
    Attributes:
        id: Уникальный ID связи
        user_id: ID пользователя
        role: Роль пользователя
        assigned_at: Дата назначения роли
        assigned_by: Кто назначил роль (опционально)
    """
    __tablename__ = 'user_roles'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True), 
        ForeignKey('users.id', ondelete='CASCADE'), 
        nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now(), 
        nullable=False
    )
    assigned_by: Mapped[Optional[UUIDType]] = mapped_column(
        PG_UUID(as_uuid=True), 
        nullable=True
    )  # кто назначил (опционально)

    # Связь
    user: Mapped["User"] = relationship("User", back_populates="roles")

    def __init__(self, **kwargs):
        """
        Инициализация с валидацией роли.
        
        Args:
            **kwargs: Параметры для инициализации
            
        Raises:
            ValueError: Если передана невалидная роль
        """
        role = kwargs.get('role')
        if role and role not in [r.value for r in UserRole]:
            raise ValueError(f"Invalid role: {role}. Valid roles are: {[r.value for r in UserRole]}")
        super().__init__(**kwargs)

    __table_args__ = (
        Index('idx_user_roles_user_id', 'user_id'),
        Index('idx_user_roles_role', 'role'),
        # Можно добавить уникальность: один пользователь не может иметь одну роль дважды
        Index('uq_user_role', 'user_id', 'role', unique=True),
    )


class User(Database.Base):
    """
    Модель пользователя системы.
    
    Attributes:
        id: Уникальный UUID пользователя
        email: Email для входа
        phone: Номер телефона (для 2FA и уведомлений)
        hashed_password: Хэш пароля (bcrypt)
        full_name: ФИО (для физлиц) / Название компании (для юрлиц)
        entity_type: Тип сущности ('individual', 'self_employed', 'legal_entity')
        inn: ИНН (опционально для физлиц, обязательно для юрлиц)
        kpp: КПП (только для юрлиц, nullable)
        legal_address: Юридический адрес (юрлица)
        tax_rate: Налоговая ставка в долях (например, 0.2 = 20%)
        timezone: Часовой пояс
        created_at: Дата регистрации
        is_active: Активен ли аккаунт
        is_staff: Является ли сотрудником системы
        staff_id: Внутренний ID сотрудника
        department: Отдел/Департамент
        position: Должность
    """
    __tablename__ = 'users'

    # Primary key as UUID according to specification
    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4, 
        comment="Уникальный ID пользователя"
    )
    
    # Authentication fields - both unique
    email: Mapped[str] = mapped_column(
        String(254), 
        unique=True, 
        nullable=False, 
        index=True, 
        comment="Email для входа"
    )
    phone: Mapped[str] = mapped_column(
        String(20), 
        unique=True, 
        nullable=False, 
        index=True, 
        comment="Номер телефона (для 2FA и уведомлений)"
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), 
        nullable=False, 
        comment="Хэш пароля (bcrypt)"
    )
    
    # User info fields
    full_name: Mapped[str] = mapped_column(
        String(255), 
        nullable=False, 
        comment="ФИО (для физлиц) / Название компании (для юрлиц)"
    )
    entity_type: Mapped[str] = mapped_column(
        String(20), 
        nullable=False, 
        index=True, 
        comment="'individual', 'self_employed', 'legal_entity'"
    )
    
    # Legal entity fields
    inn: Mapped[Optional[str]] = mapped_column(
        String(12), 
        nullable=True, 
        comment="ИНН (опционально для физлиц, обязательно для юрлиц)"
    )
    kpp: Mapped[Optional[str]] = mapped_column(
        String(9), 
        nullable=True, 
        comment="КПП (только для юрлиц, nullable)"
    )
    legal_address: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True, 
        comment="Юридический адрес (юрлица)"
    )

    # Налоговая ставка в долях (например, 0.2 = 20%)
    tax_rate: Mapped[Optional[float]] = mapped_column(Float, default=0.2, nullable=True)
    
    # System fields
    timezone: Mapped[str] = mapped_column(
        String(50), 
        default="Europe/Moscow", 
        nullable=False, 
        comment="Часовой пояс"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now(), 
        nullable=False, 
        comment="Дата регистрации"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        default=True, 
        nullable=False, 
        comment="Активен ли аккаунт"
    )
    
    # Staff fields
    is_staff: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        nullable=False, 
        comment="Является ли сотрудником системы"
    )
    staff_id: Mapped[Optional[str]] = mapped_column(
        String(50), 
        nullable=True, 
        unique=True, 
        comment="Внутренний ID сотрудника"
    )
    department: Mapped[Optional[str]] = mapped_column(
        String(100), 
        nullable=True, 
        comment="Отдел/Департамент"
    )
    position: Mapped[Optional[str]] = mapped_column(
        String(100), 
        nullable=True, 
        comment="Должность"
    )

    roles: Mapped[List["UserRoleAssociation"]] = relationship(
        "UserRoleAssociation",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    api_tokens: Mapped[List["APIToken"]] = relationship(
        "APIToken", 
        back_populates="user", 
        cascade="all, delete-orphan"
    )

    subscription: Mapped["Subscription"] = relationship(
        "Subscription",
        back_populates="user", 
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    sync_states: Mapped[List["UserSyncState"]] = relationship(
        "UserSyncState",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Composite indexes for better query performance
    __table_args__ = (
        # Unique constraint for phone/email combination (additional protection)
        Index('idx_users_phone_email_unique', 'phone', 'email', unique=True),
        
        # Index for active users by entity type (common for reports)
        Index('idx_users_active_entity', 'is_active', 'entity_type'),
        
        # Index for legal entities by INN/KPP
        Index('idx_users_legal_info', 'entity_type', 'inn', 'kpp'),
        
        # Covering index for common auth queries
        Index('idx_users_auth', 'email', 'phone', 'is_active'),
        
        # Index for staff users
        Index('idx_users_staff', 'is_staff', 'department'),
        
        # Index for staff_id searches
        Index('idx_users_staff_id', 'staff_id'),
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.primary_role})>"

    @property
    def is_legal_entity(self) -> bool:
        """
        Проверяет, является ли пользователь юридическим лицом.
        
        Returns:
            True если пользователь юрлицо, иначе False
        """
        return self.entity_type == EntityType.LEGAL_ENTITY.value

    @property
    def is_individual(self) -> bool:
        """
        Проверяет, является ли пользователь физическим лицом.
        
        Returns:
            True если пользователь физлицо, иначе False
        """
        return self.entity_type == EntityType.INDIVIDUAL.value

    @property
    def is_self_employed(self) -> bool:
        """
        Проверяет, является ли пользователь самозанятым.
        
        Returns:
            True если пользователь самозанятый, иначе False
        """
        return self.entity_type == EntityType.SELF_EMPLOYED.value

    @property
    def primary_role(self) -> str:
        """
        Основная роль пользователя (самая высокая привилегия).
        
        Returns:
            Строка с основной ролью пользователя
        """
        if not self.roles:
            return UserRole.USER.value
        role_priority = {
            UserRole.SUPER_ADMIN.value: 6,
            UserRole.ADMIN.value: 5,
            UserRole.MANAGER.value: 4,
            UserRole.SUPPORT.value: 3,
            UserRole.ANALYST.value: 2,
            UserRole.USER.value: 1
        }
        return max(self.roles, key=lambda r: role_priority.get(r.role, 0)).role

    def has_role(self, role: UserRole) -> bool:
        """
        Проверить, есть ли у пользователя указанная роль.
        
        Args:
            role: Роль для проверки
            
        Returns:
            True если роль есть, иначе False
        """
        return any(user_role.role == role.value for user_role in self.roles)

    def has_any_role(self, roles: List[UserRole]) -> bool:
        """
        Проверить, есть ли у пользователя любая из указанных ролей.
        
        Args:
            roles: Список ролей для проверки
            
        Returns:
            True если есть хотя бы одна роль, иначе False
        """
        return any(self.has_role(role) for role in roles)

    def can_manage_users(self) -> bool:
        """
        Может ли управлять пользователями.
        
        Returns:
            True если может управлять пользователями, иначе False
        """
        return self.has_any_role([UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER])

    def can_view_reports(self) -> bool:
        """
        Может ли просматривать отчеты.
        
        Returns:
            True если может просматривать отчеты, иначе False
        """
        return self.has_any_role([UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYST])

    def can_manage_system(self) -> bool:
        """
        Может ли управлять системой.
        
        Returns:
            True если может управлять системой, иначе False
        """
        return self.has_any_role([UserRole.SUPER_ADMIN, UserRole.ADMIN])

    def get_contact_info(self) -> dict:
        """
        Получить контактную информацию пользователя.
        
        Returns:
            Словарь с контактной информацией
        """
        return {
            'email': self.email,
            'phone': self.phone,
            'full_name': self.full_name,
            'position': self.position,
            'department': self.department
        }