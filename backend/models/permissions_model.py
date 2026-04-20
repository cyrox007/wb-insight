# Таблица для разрешений (если нужна детальная система прав)
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Table, Text, func
from database import Database


class Permission(Database.Base):
    __tablename__ = 'permissions'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), default=func.now())

# Таблица для связи ролей и разрешений
role_permissions = Table(
    'role_permissions',
    Database.Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('role', String(20), nullable=False),
    Column('permission_id', Integer, ForeignKey('permissions.id')),
    Index('idx_role_permissions', 'role', 'permission_id'),
)