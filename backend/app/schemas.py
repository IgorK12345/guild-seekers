from uuid import UUID
from pydantic import BaseModel, Field, field_validator

class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r'^[a-zA-Z0-9_]+$')
    password: str = Field(min_length=8, max_length=128)

class Register(Credentials):
    name: str = Field(min_length=2, max_length=32)

    @field_validator('name')
    @classmethod
    def name_clean(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Введите имя героя')
        return value

class Attack(BaseModel):
    request_id: UUID

class MonsterAttack(Attack):
    monster_id: int = Field(gt=0)

class Message(BaseModel):
    text: str = Field(min_length=1, max_length=300)

    @field_validator('text')
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Сообщение пустое')
        return value
