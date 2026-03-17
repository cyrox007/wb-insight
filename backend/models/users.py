from uuid import uuid4
from enum import Enum

from sqlalchemy import UUID, Boolean, Column, DateTime, String, Text, Index, Integer, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Database

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


# Таблица для связи многие-ко-многим пользователей и ролей
class UserRoleAssociation(Database.Base):
    __tablename__ = 'user_roles'

    id = Column(Integer, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    role = Column(String(20), nullable=False)
    assigned_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    assigned_by = Column(UUID(as_uuid=True), nullable=True)  # кто назначил (опционально)

    # Связь
    user = relationship("User", back_populates="roles")

    # Валидация на уровне Python (опционально)
    def __init__(self, **kwargs):
        role = kwargs.get('role')
        if role and role not in [r.value for r in UserRole]:
            raise ValueError(f"Invalid role: {role}")
        super().__init__(**kwargs)

    __table_args__ = (
        Index('idx_user_roles_user_id', 'user_id'),
        Index('idx_user_roles_role', 'role'),
        # Можно добавить уникальность: один пользователь не может иметь одну роль дважды
        Index('uq_user_role', 'user_id', 'role', unique=True),
    )


class User(Database.Base):
    __tablename__ = 'users'

    # Primary key as UUID according to specification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, comment="Уникальный ID пользователя")
    
    # Authentication fields - both unique
    email = Column(String(254), unique=True, nullable=False, index=True, comment="Email для входа")
    phone = Column(String(20), unique=True, nullable=False, index=True, comment="Номер телефона (для 2FA и уведомлений)")
    hashed_password = Column(String(255), nullable=False, comment="Хэш пароля (bcrypt)")
    
    # User info fields
    full_name = Column(String(255), nullable=False, comment="ФИО (для физлиц) / Название компании (для юрлиц)")
    entity_type = Column(String(20), nullable=False, index=True, comment="'individual', 'self_employed', 'legal_entity'")
    
    # Legal entity fields
    inn = Column(String(12), nullable=True, comment="ИНН (опционально для физлиц, обязательно для юрлиц)")
    kpp = Column(String(9), nullable=True, comment="КПП (только для юрлиц, nullable)")
    legal_address = Column(Text, nullable=True, comment="Юридический адрес (юрлица)")
    
    # System fields
    timezone = Column(String(50), default="Europe/Moscow", nullable=False, comment="Часовой пояс")
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False, comment="Дата регистрации")
    is_active = Column(Boolean, default=True, nullable=False, comment="Активен ли аккаунт")
    
    # Staff fields
    is_staff = Column(Boolean, default=False, nullable=False, comment="Является ли сотрудником системы")
    staff_id = Column(String(50), nullable=True, unique=True, comment="Внутренний ID сотрудника")
    department = Column(String(100), nullable=True, comment="Отдел/Департамент")
    position = Column(String(100), nullable=True, comment="Должность")

    roles = relationship(
        "UserRoleAssociation",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    api_tokens = relationship(
        "APIToken", 
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
    def is_legal_entity(self):
        return self.entity_type == EntityType.LEGAL_ENTITY.value

    @property
    def is_individual(self):
        return self.entity_type == EntityType.INDIVIDUAL.value

    @property
    def is_self_employed(self):
        return self.entity_type == EntityType.SELF_EMPLOYED.value

    @property
    def primary_role(self):
        """Основная роль пользователя (самая высокая привилегия)"""
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
        return max(self.roles, key=lambda r: role_priority.get(r.role, 0))

    def has_role(self, role):
        """Проверить, есть ли у пользователя указанная роль"""
        return any(user_role.role == role.value for user_role in self.roles)

    def has_any_role(self, roles):
        """Проверить, есть ли у пользователя любая из указанных ролей"""
        return any(self.has_role(role) for role in roles)

    def can_manage_users(self):
        """Может ли управлять пользователями"""
        return self.has_any_role([UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER])

    def can_view_reports(self):
        """Может ли просматривать отчеты"""
        return self.has_any_role([UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYST])

    def can_manage_system(self):
        """Может ли управлять системой"""
        return self.has_any_role([UserRole.SUPER_ADMIN, UserRole.ADMIN])

    def get_contact_info(self):
        """Получить контактную информацию пользователя"""
        return {
            'email': self.email,
            'phone': self.phone,
            'full_name': self.full_name,
            'position': self.position,
            'department': self.department
        }