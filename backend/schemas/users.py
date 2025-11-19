from fastapi import status, HTTPException
from pydantic import BaseModel, field_validator, ConfigDict
import re
from uuid import uuid4
from datetime import datetime
from typing import Optional
from enum import Enum


class EntityType(str, Enum):
    """Типы юридических лиц для пользователей"""
    INDIVIDUAL = "individual"        # Физическое лицо
    SELF_EMPLOYED = "self_employed"  # Самозанятый
    LEGAL_ENTITY = "legal_entity"    # Юридическое лицо


class UserCreateRequest(BaseModel):
    """
    Модель запроса для создания нового пользователя
    
    Attributes:
        email: Email пользователя (должен быть уникальным)
        phone: Номер телефона (должен быть уникальным)  
        full_name: ФИО или название компании
        entity_type: Тип пользователя (individual/self_employed/legal_entity)
        inn: ИНН (обязателен для юрлиц)
        kpp: КПП (только для юрлиц)
        legal_address: Юридический адрес (обязателен для юрлиц)
        timezone: Часовой пояс
    """
    
    # Основные поля (обязательные)
    email: str
    """Email пользователя. Должен быть уникальным в системе"""
    
    phone: str
    """Номер телефона. Должен быть уникальным в системе. Формат: +79991234567"""
    
    full_name: str
    """Полное имя пользователя. Для физлиц - ФИО, для юрлиц - название компании"""

    password: str
    
    # Юридические поля (опциональные с умолчаниями)
    entity_type: EntityType = EntityType.INDIVIDUAL
    """Тип пользователя: физическое лицо, самозанятый или юридическое лицо"""
    
    inn: Optional[str] = None
    """ИНН (Индивидуальный номер налогоплательщика). 
    Обязателен для юридических лиц, опционален для физических"""
    
    kpp: Optional[str] = None
    """КПП (Код причины постановки на учет). 
    Только для юридических лиц, должен быть 9 цифр"""
    
    legal_address: Optional[str] = None
    """Юридический адрес. Обязателен для юридических лиц"""
    
    timezone: str = "Europe/Moscow"
    """Часовой пояс пользователя. По умолчанию Московское время"""
    
    # Конфигурация Pydantic
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    
                    "email": "ivan.ivanov@example.com",
                    "phone": "+79991234567", 
                    "full_name": "Иван Иванов",
                    "password": "securepassword123",
                    "entity_type": "individual",
                    "timezone": "Europe/Moscow"
                    
                },
                {
                    "summary": "Юридическое лицо",
                    "value": {
                        "email": "company@example.com",
                        "phone": "+79997654321",
                        "full_name": "ООО 'Ромашка'", 
                        "password": "securepassword123",
                        "entity_type": "legal_entity",
                        "inn": "1234567890",
                        "kpp": "123456789",
                        "legal_address": "г. Москва, ул. Примерная, д. 1",
                        "timezone": "Europe/Moscow"
                    }
                }
            ]
        }
    )

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """
        Валидация email адреса
        
        Проверяет:
        - Соответствие базовому формату email
        - Приводит к нижнему регистру
        - Убирает лишние пробелы
        
        Args:
            v: Входной email
            
        Returns:
            str: Нормализованный email
            
        Raises:
            ValueError: Если email не соответствует формату
        """
        if not v:
            raise ValueError('Email cannot be empty')
        
        # Базовая проверка формата email
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format. Example: user@example.com')
        
        return v.lower().strip()

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """
        Валидация и нормализация номера телефона
        
        Преобразует номер к единому формату:
        - Убирает все нецифровые символы кроме +
        - Проверяет минимальную длину
        - Обеспечивает единый формат хранения
        
        Args:
            v: Входной номер телефона
            
        Returns:
            str: Нормализованный номер телефона
            
        Raises:
            ValueError: Если номер слишком короткий или невалидный
        """
        if not v:
            raise ValueError('Phone number cannot be empty')
        
        # Убираем все символы кроме цифр и +
        cleaned = re.sub(r'[^\d+]', '', v)
        
        # Проверяем длину (минимум 10 цифр без кода страны)
        digits_only = re.sub(r'\D', '', v)
        if len(digits_only) < 10:
            raise ValueError('Phone number too short. Minimum 10 digits required')
        
        # Если нет кода страны, добавляем +7 для России
        if not cleaned.startswith('+'):
            cleaned = '+7' + digits_only[-10:]
        
        return cleaned

    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        """
        Валидация полного имени
        
        Проверяет:
        - Не пустое значение
        - Минимальную и максимальную длину
        - Убирает лишние пробелы
        
        Args:
            v: Входное полное имя
            
        Returns:
            str: Нормализованное полное имя
        """
        if not v or not v.strip():
            raise ValueError('Full name cannot be empty')
        
        cleaned = ' '.join(v.strip().split())  # Убирает лишние пробелы
        
        if len(cleaned) < 2:
            raise ValueError('Full name too short')
        if len(cleaned) > 255:
            raise ValueError('Full name too long (max 255 characters)')
            
        return cleaned

    @field_validator('inn')
    @classmethod
    def validate_inn(cls, v: Optional[str], info) -> Optional[str]:
        """
        Валидация ИНН в зависимости от типа пользователя
        
        Проверяет:
        - Для юрлиц: ИНН обязателен, 10 цифр
        - Для физлиц: ИНН опционален, 12 цифр
        - Только цифры
        
        Args:
            v: ИНН для проверки
            info: Информация о других полях модели
            
        Returns:
            Optional[str]: Валидированный ИНН или None
        """
        if v is None:
            # Проверяем обязательность ИНН для юрлиц
            if info.data.get('entity_type') == EntityType.LEGAL_ENTITY:
                raise ValueError('INN is required for legal entities')
            return None
        
        # Проверяем что ИНН состоит только из цифр
        if not v.isdigit():
            raise ValueError('INN must contain only digits')
        
        # Проверяем длину в зависимости от типа пользователя
        entity_type = info.data.get('entity_type')
        if entity_type == EntityType.LEGAL_ENTITY and len(v) != 10:
            raise ValueError('INN for legal entities must be 10 digits')
        elif entity_type in [EntityType.INDIVIDUAL, EntityType.SELF_EMPLOYED] and len(v) != 12:
            raise ValueError('INN for individuals must be 12 digits')
        
        return v

    @field_validator('kpp')
    @classmethod
    def validate_kpp(cls, v: Optional[str], info) -> Optional[str]:
        """
        Валидация КПП
        
        Проверяет:
        - КПП разрешен только для юрлиц
        - Формат: 9 цифр
        - Только для юридических лиц
        
        Args:
            v: КПП для проверки
            info: Информация о других полях модели
        """
        if v is not None:
            if info.data.get('entity_type') != EntityType.LEGAL_ENTITY:
                raise ValueError('KPP is only allowed for legal entities')
            
            if not v.isdigit() or len(v) != 9:
                raise ValueError('KPP must be exactly 9 digits')
        
        return v

    @field_validator('legal_address')
    @classmethod
    def validate_legal_address(cls, v: Optional[str], info) -> Optional[str]:
        """
        Валидация юридического адреса
        
        Проверяет:
        - Для юрлиц адрес обязателен
        - Максимальная длина
        - Не пустое значение для юрлиц
        
        Args:
            v: Адрес для проверки
            info: Информация о других полях модели
        """
        if info.data.get('entity_type') == EntityType.LEGAL_ENTITY:
            if not v or not v.strip():
                raise ValueError('Legal address is required for legal entities')
            
            if len(v.strip()) > 500:
                raise ValueError('Legal address too long (max 500 characters)')
        
        return v.strip() if v else v
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        """Валидация пароля"""
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v
