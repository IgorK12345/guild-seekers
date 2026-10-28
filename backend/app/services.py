import math
import random
from datetime import timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError, VerificationError
from fastapi import HTTPException
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError
from .models import *
from .balance import *

passwords = PasswordHasher()

def require(value, message='Объект не найден', status=404):
    if value is None:
        raise HTTPException(status, message)
    return value

def lock_character(db, user_id):
    return require(db.scalar(select(Character).where(Character.user_id == user_id).with_for_update()))

def add_xp(character, xp):
    character.xp += xp
    character.level = level_for(character.xp)

def ensure_idle(character):
    if character.battle_until and now() < character.battle_until:
        raise HTTPException(409, 'Бой ещё идёт. Дождитесь завершения обмена ударами.')

def regenerate(character):
    moment = now()
    start = max(character.hp_updated_at, character.battle_until or character.hp_updated_at)
    if moment > start:
        character.hp = min(character.max_hp, character.hp + (moment-start).total_seconds() * regen_rate(character.level, character.max_hp))
        character.hp_updated_at = moment

def stats(db, character):
    rows = db.execute(select(InventoryItem, Item).join(Item).where(
        InventoryItem.character_id == character.id, InventoryItem.equipped.is_(True))).all()
    return dict(attack=BASE_ATTACK + sum(item_power(i.attack, e.stars) for e, i in rows),
                defense=sum(item_power(i.defense, e.stars) for e, i in rows))

def progress_for(db, character, location_id):
    value = db.scalar(select(CharacterLocation).where(CharacterLocation.character_id == character.id,
                                                     CharacterLocation.location_id == location_id))
    if value is None:
        value = CharacterLocation(character_id=character.id, location_id=location_id,
                                  kills=0, elixirs=0, miniboss_defeated=False, next_elixir_at=random.randint(3,5))
        db.add(value)
        db.flush()
    return value

def unlocked(db, character, location_id):
    if location_id == 1:
        return True
    previous = db.scalar(select(CharacterLocation).where(CharacterLocation.character_id == character.id,
                                                         CharacterLocation.location_id == location_id-1))
    return bool(previous and previous.miniboss_defeated)

def grant_item(db, character, item_id, stars=1, count=1):
    entry = db.scalar(select(InventoryItem).where(InventoryItem.character_id == character.id,
                                                  InventoryItem.item_id == item_id, InventoryItem.stars == stars))
    if entry:
        entry.quantity += count
    else:
        entry = InventoryItem(character_id=character.id, item_id=item_id, stars=stars, quantity=count, equipped=False)
        db.add(entry)
        db.flush()
    return entry

def character_view(db, character):
    regenerate(character)
    active = bool(character.battle_until and character.battle_until > now())
    result = dict(id=character.id, name=character.name, level=character.level, xp=character.xp,
                  xp_in_level=character.xp-level_start(character.level), xp_next=300*character.level,
                  hp=math.floor(character.hp), max_hp=character.max_hp, potions=character.potions,
                  regen_per_10s=round(regen_rate(character.level, character.max_hp)*10, 2),
                  regen_percent=round(1 + .1*(character.level-1), 1), in_battle=active,
                  battle_until=character.battle_until.isoformat() if active else None,
                  elixirs=(character.max_hp-BASE_HP)//ELIXIR_HP, **stats(db, character))
    db.commit()
    return result

class AuthService:
    def register(self, db, data):
        user = User(username=data.username.lower(), password_hash=passwords.hash(data.password))
        try:
            db.add(user)
            db.flush()
            character = Character(user_id=user.id, name=data.name)
            db.add(character)
            db.flush()
            grant_item(db, character, 1).equipped = True
            for quest in db.scalars(select(Quest)).all():
                db.add(CharacterQuest(character_id=character.id, quest_id=quest.id))
            for loc in db.scalars(select(Location)).all():
                progress_for(db, character, loc.id)
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'Этот логин уже занят')
        return user

    def login(self, db, data):
        user = db.scalar(select(User).where(User.username == data.username.lower()))
        if not user:
            passwords.hash(data.password)
            raise HTTPException(401, 'Неверный логин или пароль')
        try:
            passwords.verify(user.password_hash, data.password)
        except (VerifyMismatchError, InvalidHashError, VerificationError):
            raise HTTPException(401, 'Неверный логин или пароль')
        return user

class InventoryService:
    def list(self, db, character):
        return [dict(id=e.id, item_id=i.id, name=i.name, slot=i.slot, attack=item_power(i.attack,e.stars),
                     defense=item_power(i.defense,e.stars), icon=i.icon, equipped=e.equipped,
                     stars=e.stars, quantity=e.quantity, can_merge=e.stars < 5 and e.quantity >= 3)
                for e, i in db.execute(select(InventoryItem,Item).join(Item).where(
                    InventoryItem.character_id==character.id).order_by(Item.id, InventoryItem.stars.desc())).all()]

    def equip_entry(self, db, character, entry):
        slot = db.get(Item,entry.item_id).slot
        for other, kind in db.execute(select(InventoryItem,Item).join(Item).where(
                InventoryItem.character_id==character.id, InventoryItem.equipped.is_(True))).all():
            if kind.slot == slot:
                other.equipped = False
        entry.equipped = True

    def equip(self, db, character, entry_id, enabled):
        ensure_idle(character)
        entry = require(db.scalar(select(InventoryItem).where(InventoryItem.id==entry_id,
                       InventoryItem.character_id==character.id)), 'Предмет не найден')
        if enabled:
            self.equip_entry(db,character,entry)
        else:
            entry.equipped = False
        db.commit()
        return {'message':'Предмет надет' if enabled else 'Предмет снят'}

    def merge(self, db, character, entry_id):
        ensure_idle(character)
        entry = require(db.scalar(select(InventoryItem).where(InventoryItem.id==entry_id,
                       InventoryItem.character_id==character.id)), 'Предмет не найден')
        if entry.stars >= 5 or entry.quantity < 3:
            raise HTTPException(400, 'Нужны 3 одинаковые копии. Максимум — 5 звёзд.')
        equipped, item_id, stars = entry.equipped, entry.item_id, entry.stars+1
        entry.equipped = False if equipped else entry.equipped
        if entry.quantity == 3:
            db.delete(entry)
        else:
            entry.quantity -= 3
        db.flush()
        upgraded = grant_item(db,character,item_id,stars)
        if equipped:
            self.equip_entry(db,character,upgraded)
        db.commit()
        return {'message':f'Предмет улучшен до {stars} звёзд!', 'stars':stars}

    def heal(self, db, character):
        ensure_idle(character)
        regenerate(character)
        if character.potions <= 0:
            raise HTTPException(400, 'Нет лечебных зелий. Здоровье постепенно восстанавливается само.')
        if character.hp >= character.max_hp:
            raise HTTPException(400, 'Здоровье уже полное')
        character.potions -= 1
        character.hp = min(character.max_hp,character.hp+math.ceil(character.max_hp*POTION_HEAL))
        db.commit()
        return {'message':'Зелье использовано: восстановлено до 30% максимального HP.'}

class QuestService:
    def list(self, db, character):
        return [dict(id=q.id,title=q.title,description=q.description,target=q.target,progress=p.progress,
                     claimed=p.claimed,xp_reward=q.xp_reward)
                for p,q in db.execute(select(CharacterQuest,Quest).join(Quest).where(
                    CharacterQuest.character_id==character.id).order_by(Quest.id)).all()]

    def progress(self, db, character, monster_id):
        for p,q in db.execute(select(CharacterQuest,Quest).join(Quest).where(
                CharacterQuest.character_id==character.id,Quest.monster_id==monster_id)).all():
            p.progress = min(q.target,p.progress+1)

    def claim(self, db, character, quest_id):
        ensure_idle(character)
        p = require(db.scalar(select(CharacterQuest).where(CharacterQuest.character_id==character.id,
                                                         CharacterQuest.quest_id==quest_id)))
        q = db.get(Quest,quest_id)
        if p.claimed:
            raise HTTPException(409,'Награда уже получена')
        if p.progress < q.target:
            raise HTTPException(400,'Задание ещё не выполнено')
        regenerate(character)  # Accrue old-rate regeneration before changing level.
        p.claimed = True
        add_xp(character,q.xp_reward)
        db.commit()
        return {'message':f'Получено {q.xp_reward} опыта'}

class CombatService:
    def previous(self,db,character,request_id,monster_id=None,boss=False):
        previous = db.scalar(select(Battle).where(Battle.character_id==character.id,
                                                 Battle.request_id==str(request_id)))
        if previous:
            if (boss and previous.boss_id is None) or (not boss and previous.monster_id != monster_id):
                raise HTTPException(409,'Этот идентификатор уже использован для другого действия')
            return previous.result

    def prepare(self,character):
        ensure_idle(character)
        regenerate(character)
        if math.floor(character.hp) < 1:
            raise HTTPException(400,'Вы повержены. Дождитесь восстановления хотя бы 1 HP или используйте зелье.')

    def finish(self,character,result):
        start = now()
        end = start+timedelta(seconds=len(result['frames'])*FRAME_SECONDS)
        character.battle_until = end
        character.hp_updated_at = end
        result.update(started_at=start.isoformat(),ends_at=end.isoformat(),frame_seconds=FRAME_SECONDS,
                      final_hp=math.floor(character.hp),final_max_hp=character.max_hp)
        return result

    def fight(self,db,character,monster_id,request_id):
        previous = self.previous(db,character,request_id,monster_id)
        if previous:
            return previous
        monster = require(db.get(Monster,monster_id))
        if not unlocked(db,character,monster.location_id):
            raise HTTPException(403,'Сначала победите мини-босса предыдущей локации')
        progress = progress_for(db,character,monster.location_id)
        if monster.is_miniboss and progress.miniboss_defeated:
            raise HTTPException(409,'Этот мини-босс уже побеждён')
        self.prepare(character)
        hero = stats(db,character)
        initial_hp, initial_max = math.floor(character.hp), character.max_hp
        frames,hp,enemy_hp = simulate(initial_hp,monster.hp,hero['attack'],hero['defense'],monster.attack,monster.defense)
        character.hp = hp
        won = enemy_hp == 0
        drops = []
        old_level = character.level
        if won:
            add_xp(character,monster.xp_reward)
            QuestService().progress(db,character,monster.id)
            if monster.is_miniboss:
                progress.miniboss_defeated = True
                drops.append('Следующая локация открыта' if monster.location_id < 3 else 'Все локации пройдены!')
            else:
                grant_item(db,character,monster.drop_item_id)
                drops.append(db.get(Item,monster.drop_item_id).name+' ★')
                progress.kills += 1
                if random.random() < POTION_CHANCE:
                    character.potions += 1
                    drops.append('Зелье лечения ×1')
                if progress.elixirs < 5 and progress.kills >= progress.next_elixir_at:
                    progress.elixirs += 1
                    progress.next_elixir_at = progress.kills + (random.randint(3,5) if progress.elixirs < 4 else random.randint(6,10))
                    character.max_hp += ELIXIR_HP
                    character.hp += ELIXIR_HP
                    drops.append('Эликсир жизненной силы: +10 к максимальному HP (применён)')
        result = self.finish(character,dict(won=won,enemy=monster.name,enemy_icon=monster.icon,
                    hero_name=character.name,initial_hp=initial_hp,initial_max_hp=initial_max,
                    enemy_hp=monster.hp,enemy_max_hp=monster.hp,frames=frames,
                    log=[f"{'Вы' if f['actor']=='hero' else monster.name}: {f['damage']} урона" for f in frames],
                    xp=monster.xp_reward if won else 0,drops=drops,level_up=old_level!=character.level,level=character.level,
                    message='Победа!' if won else 'Поражение. Опыт и вещи сохранены.',kind='miniboss' if monster.is_miniboss else 'monster'))
        db.add(Battle(character_id=character.id,monster_id=monster.id,request_id=str(request_id),won=won,
                      damage=monster.hp-enemy_hp,result=result))
        db.commit()
        return result

class BossService:
    def current(self,db):
        db.execute(text('SELECT pg_advisory_xact_lock(718232)'))
        boss = require(db.scalar(select(WorldBoss).order_by(WorldBoss.id.desc()).limit(1).with_for_update()))
        if boss.defeated_at and now() >= boss.defeated_at+timedelta(seconds=60):
            variant = (boss.variant+1)%len(BOSSES)
            boss = WorldBoss(**BOSSES[variant],variant=variant,hp=5000,max_hp=5000)
            db.add(boss)
            db.flush()
        return boss

    def view(self,db):
        boss = self.current(db)
        damage = func.sum(Battle.damage).label('damage')
        leaders = db.execute(select(Character.name,damage).join(Battle,Battle.character_id==Character.id)
            .where(Battle.boss_id==boss.id).group_by(Character.id,Character.name)
            .order_by(damage.desc(),Character.id).limit(10)).all()
        result = dict(id=boss.id,name=boss.name,hp=boss.hp,max_hp=boss.max_hp,attack=boss.attack,icon=boss.icon,
                      variant=boss.variant,respawn_at=(boss.defeated_at+timedelta(seconds=60)).isoformat() if boss.defeated_at else None,
                      contributors=[dict(name=n,damage=d) for n,d in leaders])
        db.commit()
        return result

    def attack(self,db,character,request_id):
        combat = CombatService()
        previous = combat.previous(db,character,request_id,boss=True)
        if previous:
            return previous
        combat.prepare(character)
        boss = self.current(db)
        if boss.hp == 0:
            raise HTTPException(409,'Босс повержен. Новый появится через минуту')
        hero = stats(db,character)
        initial_hp,initial_enemy = math.floor(character.hp),boss.hp
        frames,hp,enemy_hp = simulate(initial_hp,boss.hp,hero['attack'],hero['defense'],boss.attack,single_exchange=True)
        character.hp, boss.hp = hp,enemy_hp
        if boss.hp == 0:
            boss.defeated_at = now()
        damage = initial_enemy-enemy_hp
        xp = max(1,damage//2)
        add_xp(character,xp)
        result = combat.finish(character,dict(message='Вы повержены. Опыт и вещи сохранены.' if hp==0 else 'Обмен ударами завершён',
             won=boss.hp==0,kind='boss',enemy=boss.name,enemy_icon=boss.icon,hero_name=character.name,
             initial_hp=initial_hp,initial_max_hp=character.max_hp,enemy_hp=initial_enemy,enemy_max_hp=boss.max_hp,
             frames=frames,damage=damage,xp=xp,hp=boss.hp,drops=[],log=[],level_up=False,level=character.level))
        db.add(Battle(character_id=character.id,boss_id=boss.id,request_id=str(request_id),damage=damage,won=boss.hp==0,result=result))
        db.commit()
        return result
