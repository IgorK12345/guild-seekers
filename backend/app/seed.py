from sqlalchemy import select, text
from .database import SessionLocal
from .models import Location, Monster, Item, Quest, WorldBoss
from .balance import BOSSES

def seed():
    with SessionLocal.begin() as db:
        db.execute(text('SELECT pg_advisory_xact_lock(718231)'))
        for entity in [
            Location(id=1, name='Тихий лес', description='Среди старых сосен начинается путь искателя.', min_level=1, icon='🌲'),
            Location(id=2, name='Забытые руины', description='Каменные своды хранят следы древней войны.', min_level=2, icon='🏛'),
            Location(id=3, name='Пепельные горы', description='За перевалом ждут самые опасные противники.', min_level=3, icon='🌋'),
            Item(id=1, name='Учебный меч', slot='weapon', attack=2, defense=0, icon='🗡'),
            Item(id=2, name='Лесной клинок', slot='weapon', attack=8, defense=0, icon='⚔'),
            Item(id=3, name='Кожаный доспех', slot='armor', attack=0, defense=4, icon='🛡'),
            Item(id=4, name='Меч стража', slot='weapon', attack=12, defense=0, icon='⚔'),
            Item(id=5, name='Стальной доспех', slot='armor', attack=0, defense=6, icon='🛡'),
            Item(id=7, name='Обсидиановый доспех', slot='armor', attack=0, defense=9, icon='🛡'),
            Item(id=6, name='Клинок пламени', slot='weapon', attack=18, defense=0, icon='🔥'),
        ]:
            db.merge(entity)
        db.flush()
        for i, loc, name, hp, attack, xp, item, icon, mini in [
            (1, 1, 'Лесной слизень', 24, 6, 30, 2, '🟢', False),
            (2, 1, 'Серый волк', 24, 6, 30, 3, '🐺', False),
            (3, 2, 'Костяной страж', 48, 14, 60, 4, '💀', False),
            (4, 2, 'Каменный голем', 48, 14, 60, 5, '🗿', False),
            (5, 3, 'Огненный дух', 90, 22, 90, 6, '🔥', False),
            (6, 3, 'Горная виверна', 90, 22, 90, 7, '🐉', False),
            (7, 1, 'Хранитель чащи', 110, 33, 90, 2, '🦌', True),
            (8, 2, 'Железный смотритель', 186, 41, 180, 4, '🤖', True),
            (9, 3, 'Сердце вулкана', 270, 55, 270, 6, '👹', True)]:
            db.merge(Monster(id=i, location_id=loc, name=name, hp=hp, attack=attack, defense=0,
                             xp_reward=xp, drop_item_id=item, icon=icon, is_miniboss=mini))
        db.flush()
        for entity in [
            Quest(id=1, title='Первый контракт', description='Победите трёх лесных слизней.', monster_id=1, target=3, xp_reward=60, item_reward_id=3),
            Quest(id=2, title='Стражи прошлого', description='Победите трёх костяных стражей.', monster_id=3, target=3, xp_reward=120, item_reward_id=5),
            Quest(id=3, title='Укротитель пламени', description='Победите трёх огненных духов.', monster_id=5, target=3, xp_reward=180, item_reward_id=6),
            
        ]:
            db.merge(entity)

        if not db.scalar(select(WorldBoss.id).limit(1)):
            db.add(WorldBoss(**BOSSES[0], variant=0, hp=5000, max_hp=5000))

if __name__ == '__main__':
    seed()
