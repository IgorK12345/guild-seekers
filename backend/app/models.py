from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, Integer, Float, DateTime, Boolean, JSON, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

def now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Character(Base):
    __tablename__ = 'characters'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), unique=True)
    name: Mapped[str] = mapped_column(String(32))
    xp: Mapped[int] = mapped_column(default=0)
    level: Mapped[int] = mapped_column(default=1)
    last_action: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_chat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hp: Mapped[float] = mapped_column(Float, default=60)
    max_hp: Mapped[int] = mapped_column(default=60)
    hp_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    battle_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    potions: Mapped[int] = mapped_column(default=0)
    __table_args__ = (CheckConstraint('xp >= 0 AND level >= 1'),
                     CheckConstraint('hp >= 0 AND hp <= max_hp AND max_hp >= 60 AND potions >= 0', name='ck_character_health'),)

class Location(Base):
    __tablename__ = 'locations'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(255))
    min_level: Mapped[int] = mapped_column(default=1)
    icon: Mapped[str] = mapped_column(String(20))

class Item(Base):
    __tablename__ = 'items'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    slot: Mapped[str] = mapped_column(String(16))
    attack: Mapped[int] = mapped_column(default=0)
    defense: Mapped[int] = mapped_column(default=0)
    icon: Mapped[str] = mapped_column(String(20))
    __table_args__ = (CheckConstraint("slot IN ('weapon', 'armor')"),)

class Monster(Base):
    __tablename__ = 'monsters'
    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey('locations.id'))
    name: Mapped[str] = mapped_column(String(80))
    hp: Mapped[int] = mapped_column()
    attack: Mapped[int] = mapped_column()
    defense: Mapped[int] = mapped_column(default=0)
    xp_reward: Mapped[int] = mapped_column()
    drop_item_id: Mapped[int] = mapped_column(ForeignKey('items.id'))
    icon: Mapped[str] = mapped_column(String(20))
    is_miniboss: Mapped[bool] = mapped_column(Boolean, default=False)

class InventoryItem(Base):
    __tablename__ = 'inventory_items'
    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey('characters.id'), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('items.id'))
    equipped: Mapped[bool] = mapped_column(Boolean, default=False)
    stars: Mapped[int] = mapped_column(default=1)
    quantity: Mapped[int] = mapped_column(default=1)
    __table_args__ = (UniqueConstraint('character_id', 'item_id', 'stars', name='uq_inventory_stack'),
                     CheckConstraint('stars BETWEEN 1 AND 5 AND quantity > 0', name='ck_inventory_stack'),)

class CharacterLocation(Base):
    __tablename__ = 'character_locations'
    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey('characters.id'))
    location_id: Mapped[int] = mapped_column(ForeignKey('locations.id'))
    kills: Mapped[int] = mapped_column(default=0)
    elixirs: Mapped[int] = mapped_column(default=0)
    next_elixir_at: Mapped[int] = mapped_column(default=4)
    miniboss_defeated: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint('character_id', 'location_id'),
                     CheckConstraint('elixirs BETWEEN 0 AND 5 AND kills >= 0'),)

class Quest(Base):
    __tablename__ = 'quests'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255))
    monster_id: Mapped[int] = mapped_column(ForeignKey('monsters.id'))
    target: Mapped[int] = mapped_column()
    xp_reward: Mapped[int] = mapped_column()
    item_reward_id: Mapped[int] = mapped_column(ForeignKey('items.id'))

class CharacterQuest(Base):
    __tablename__ = 'character_quests'
    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey('characters.id'))
    quest_id: Mapped[int] = mapped_column(ForeignKey('quests.id'))
    progress: Mapped[int] = mapped_column(default=0)
    claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint('character_id', 'quest_id'),)

class WorldBoss(Base):
    __tablename__ = 'world_bosses'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    hp: Mapped[int] = mapped_column()
    max_hp: Mapped[int] = mapped_column()
    variant: Mapped[int] = mapped_column(default=0)
    attack: Mapped[int] = mapped_column(default=24)
    icon: Mapped[str] = mapped_column(String(20), default='🐉')
    defeated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint('hp >= 0 AND hp <= max_hp'),)

class Battle(Base):
    __tablename__ = 'battles'
    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey('characters.id'), index=True)
    monster_id: Mapped[int | None] = mapped_column(ForeignKey('monsters.id'))
    boss_id: Mapped[int | None] = mapped_column(ForeignKey('world_bosses.id'))
    request_id: Mapped[str] = mapped_column(String(36))
    damage: Mapped[int] = mapped_column(default=0)
    won: Mapped[bool] = mapped_column(default=False)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('character_id', 'request_id'), CheckConstraint('(monster_id IS NULL) <> (boss_id IS NULL)'),)

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey('characters.id'))
    text: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
