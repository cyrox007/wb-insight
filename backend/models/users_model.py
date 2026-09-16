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
    INDIVIDUAL = "individual"
    SELF_EMPLOYED = "self_employed"
    LEGAL_ENTITY = "legal_entity"


class UserRole(Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    SUPPORT = "support"
    ANALYST = "analyst"
    USER = "user"


class UserRoleAssociation(Database.Base):
    __tablename__ = 'user_roles'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    assigned_by: Mapped[Optional[UUIDType]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    user: Mapped["User"] = relationship("User", back_populates="roles")

    def __init__(self, **kwargs):
        role = kwargs.get('role')
        if role and role not in [r.value for r in UserRole]:
            raise ValueError(f"Invalid role: {role}. Valid roles are: {[r.value for r in UserRole]}")
        super().__init__(**kwargs)

    __table_args__ = (
        Index('idx_user_roles_user_id', 'user_id'),
        Index('idx_user_roles_role', 'role'),
        Index('uq_user_role', 'user_id', 'role', unique=True),
    )


class User(Database.Base):
    __tablename__ = 'users'

    id: Mapped[UUIDType] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, comment="Уникальный ID пользователя")
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True, comment="Email для входа")
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True, comment="Номер телефона (для 2FA и уведомлений)")
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False, comment="Хэш пароля (bcrypt)")
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="ФИО (для физлиц) / Название компании (для юрлиц)")
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="'individual', 'self_employed', 'legal_entity'")
    inn: Mapped[Optional[str]] = mapped_column(String(12), nullable=True, comment="ИНН (опционально для физлиц, обязательно для юрлиц)")
    kpp: Mapped[Optional[str]] = mapped_column(String(9), nullable=True, comment="КПП (только для юрлиц, nullable)")
    legal_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Юридический адрес (юрлица)")
    tax_rate: Mapped[Optional[float]] = mapped_column(Float, default=0.2, nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow", nullable=False, comment="Часовой пояс")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False, comment="Дата регистрации")
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="Момент подтверждения владения текущим email")
    pending_email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True, comment="Новый email, ожидающий подтверждения")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="Активен ли аккаунт")
    session_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False, comment="Версия security session; increment отзывает ранее выданные JWT")
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retention_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Является ли сотрудником системы")
    staff_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, unique=True, comment="Внутренний ID сотрудника")
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Отдел/Департамент")
    position: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Должность")

    roles: Mapped[List["UserRoleAssociation"]] = relationship("UserRoleAssociation", back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    api_tokens: Mapped[List["APIToken"]] = relationship("APIToken", back_populates="user", cascade="all, delete-orphan")
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="user")
    sync_states: Mapped[List["UserSyncState"]] = relationship("UserSyncState", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_users_phone_email_unique', 'phone', 'email', unique=True),
        Index('idx_users_active_entity', 'is_active', 'entity_type'),
        Index('idx_users_legal_info', 'entity_type', 'inn', 'kpp'),
        Index('idx_users_auth', 'email', 'phone', 'is_active'),
        Index('idx_users_pending_email', 'pending_email'),
        Index('idx_users_staff', 'is_staff', 'department'),
        Index('idx_users_staff_id', 'staff_id'),
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.primary_role})>"

    @property
    def is_legal_entity(self) -> bool:
        return self.entity_type == EntityType.LEGAL_ENTITY.value

    @property
    def is_individual(self) -> bool:
        return self.entity_type == EntityType.INDIVIDUAL.value

    @property
    def is_self_employed(self) -> bool:
        return self.entity_type == EntityType.SELF_EMPLOYED.value

    @property
    def primary_role(self) -> str:
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
        return any(user_role.role == role.value for user_role in self.roles)

    def has_any_role(self, roles: List[UserRole]) -> bool:
        return any(self.has_role(role) for role in roles)

    def can_manage_users(self) -> bool:
        return self.has_any_role([UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER])

    def can_view_reports(self) -> bool:
        return self.has_any_role([UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYST])

    def can_manage_system(self) -> bool:
        return self.has_any_role([UserRole.SUPER_ADMIN, UserRole.ADMIN])

    def get_contact_info(self) -> dict:
        return {'email': self.email, 'phone': self.phone, 'full_name': self.full_name, 'position': self.position, 'department': self.department}
