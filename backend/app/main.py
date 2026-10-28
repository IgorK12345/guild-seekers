from contextlib import asynccontextmanager
from typing import Annotated
from collections import OrderedDict, deque
from time import monotonic
from fastapi import FastAPI, Depends, Request, HTTPException, APIRouter
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from .config import settings, ROOT
from .database import get_db
from .models import User, Character, Location, Monster, ChatMessage, Battle, Item, now
from .schemas import Credentials, Register, MonsterAttack, Attack, Message
from .services import AuthService, InventoryService, QuestService, CombatService, BossService, lock_character, character_view, unlocked, progress_for

app = FastAPI(title='Гильдия искателей', version='1.0.0', description='Учебная многопользовательская RPG')
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, session_cookie='guild_session',
                   max_age=86400, same_site='lax', https_only=settings.secure_cookie)

# One Uvicorn process: bound in-memory buckets protect expensive password hashing.
# Caddy supplies the real client address through trusted proxy headers.
auth_attempts = OrderedDict()

@app.middleware('http')
async def protect(request: Request, call_next):
    if request.method == 'POST' and request.url.path in ('/api/auth/login', '/api/auth/register'):
        key = (request.client.host if request.client else 'unknown', request.url.path)
        moment = monotonic()
        bucket = auth_attempts.setdefault(key, deque())
        auth_attempts.move_to_end(key)
        while bucket and bucket[0] <= moment - 60:
            bucket.popleft()
        limit = 5 if request.url.path.endswith('/register') else 12
        if len(bucket) >= limit:
            return JSONResponse({'detail': 'Слишком много попыток входа или регистрации. Подождите минуту.'},
                                status_code=429, headers={'Retry-After': '60'})
        bucket.append(moment)
        if len(auth_attempts) > 10000:
            auth_attempts.popitem(last=False)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        if origin and origin != settings.public_origin:
            return JSONResponse({'detail': 'Недопустимый источник запроса'}, status_code=403)
        if request.headers.get('content-type', '').split(';')[0] != 'application/json':
            return JSONResponse({'detail': 'Ожидается application/json'}, status_code=415)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    if request.url.path.startswith('/api'):
        response.headers['Cache-Control'] = 'no-store'
    return response

DB = Annotated[Session, Depends(get_db)]

def current_user(request: Request, db: DB):
    uid = request.session.get('user_id')
    user = db.get(User, uid) if isinstance(uid, int) else None
    if not user:
        raise HTTPException(401, 'Сначала войдите в игру')
    return user

UserDep = Annotated[User, Depends(current_user)]
api = APIRouter(prefix='/api')

@api.post('/auth/register', tags=['Аккаунт'], status_code=201)
def register(data: Register, request: Request, db: DB):
    user = AuthService().register(db, data)
    request.session.clear()
    request.session['user_id'] = user.id
    return {'username': user.username}

@api.post('/auth/login', tags=['Аккаунт'])
def login(data: Credentials, request: Request, db: DB):
    user = AuthService().login(db, data)
    request.session.clear()
    request.session['user_id'] = user.id
    return {'username': user.username}

@api.post('/auth/logout', tags=['Аккаунт'])
def logout(request: Request):
    request.session.clear()
    return {'message': 'Вы вышли из игры'}

def hero(db, user):
    return db.scalar(select(Character).where(Character.user_id == user.id))

@api.get('/character', tags=['Герой'])
def character(db: DB, user: UserDep):
    return character_view(db, lock_character(db, user.id))

@api.get('/locations', tags=['Приключения'])
def locations(db: DB, user: UserDep):
    character = lock_character(db, user.id)
    result = [dict(id=loc.id, name=loc.name, description=loc.description, icon=loc.icon,
                 min_level=loc.min_level, unlocked=unlocked(db, character, loc.id),
                 elixirs=progress_for(db,character,loc.id).elixirs,
                 kills=progress_for(db,character,loc.id).kills,
                 cleared=progress_for(db,character,loc.id).miniboss_defeated,
                 monsters=[dict(id=m.id, name=m.name, hp=m.hp, attack=m.attack, defense=m.defense,
                                xp_reward=m.xp_reward, icon=m.icon, is_miniboss=m.is_miniboss,
                                drop_name=db.get(Item,m.drop_item_id).name)
                           for m in db.scalars(select(Monster).where(Monster.location_id == loc.id).order_by(Monster.id))])
            for loc in db.scalars(select(Location).order_by(Location.id))]
    db.commit()
    return result

@api.post('/battles', tags=['Приключения'])
def fight(data: MonsterAttack, db: DB, user: UserDep):
    return CombatService().fight(db, lock_character(db, user.id), data.monster_id, data.request_id)

@api.get('/battles', tags=['Приключения'])
def history(db: DB, user: UserDep):
    return [dict(id=b.id, created_at=b.created_at.isoformat(), result=b.result)
            for b in db.scalars(select(Battle).where(Battle.character_id == hero(db, user).id)
                                .order_by(Battle.id.desc()).limit(10))]

@api.get('/inventory', tags=['Инвентарь'])
def inventory(db: DB, user: UserDep):
    return InventoryService().list(db, hero(db, user))

@api.post('/inventory/{entry_id}/equip', tags=['Инвентарь'])
def equip(entry_id: int, db: DB, user: UserDep):
    return InventoryService().equip(db, lock_character(db, user.id), entry_id, True)

@api.post('/inventory/{entry_id}/unequip', tags=['Инвентарь'])
def unequip(entry_id: int, db: DB, user: UserDep):
    return InventoryService().equip(db, lock_character(db, user.id), entry_id, False)

@api.get('/quests', tags=['Задания'])
def quests(db: DB, user: UserDep):
    return QuestService().list(db, hero(db, user))

@api.post('/inventory/{entry_id}/merge', tags=['Инвентарь'])
def merge(entry_id: int, db: DB, user: UserDep):
    return InventoryService().merge(db, lock_character(db, user.id), entry_id)

@api.post('/character/heal', tags=['Герой'])
def heal(db: DB, user: UserDep):
    return InventoryService().heal(db, lock_character(db, user.id))

@api.post('/quests/{quest_id}/claim', tags=['Задания'])
def claim(quest_id: int, db: DB, user: UserDep):
    return QuestService().claim(db, lock_character(db, user.id), quest_id)

@api.get('/boss', tags=['Общий босс'])
def boss(db: DB, user: UserDep):
    return BossService().view(db)

@api.post('/boss/attack', tags=['Общий босс'])
def attack_boss(data: Attack, db: DB, user: UserDep):
    return BossService().attack(db, lock_character(db, user.id), data.request_id)

@api.get('/leaderboard', tags=['Сообщество'])
def leaderboard(db: DB, user: UserDep):
    return [dict(name=c.name, level=c.level, xp=c.xp, is_me=c.user_id == user.id)
            for c in db.scalars(select(Character).order_by(Character.xp.desc(), Character.id).limit(20))]

@api.get('/chat', tags=['Сообщество'])
def messages(db: DB, user: UserDep):
    rows = db.execute(select(ChatMessage, Character.name).join(Character)
                      .order_by(ChatMessage.id.desc()).limit(50)).all()
    return [dict(id=m.id, name=name, text=m.text, created_at=m.created_at.isoformat()) for m, name in reversed(rows)]

@api.post('/chat', tags=['Сообщество'], status_code=201)
def send_message(data: Message, db: DB, user: UserDep):
    character = lock_character(db, user.id)
    if character.last_chat and (now() - character.last_chat).total_seconds() < 1:
        raise HTTPException(429, 'Отправляйте сообщения не чаще раза в секунду')
    character.last_chat = now()
    db.add(ChatMessage(character_id=character.id, text=data.text))
    db.commit()
    return {'message': 'Сообщение отправлено'}

@app.get('/health', include_in_schema=False)
def health(db: DB):
    db.execute(text('SELECT 1'))
    return {'status': 'ok', 'database': 'postgresql'}

app.include_router(api)
app.mount('/static', StaticFiles(directory=ROOT / 'frontend'), name='static')

@app.get('/', include_in_schema=False)
def index():
    return FileResponse(ROOT / 'frontend' / 'index.html')

@app.get('/game', include_in_schema=False)
def game():
    return FileResponse(ROOT / 'frontend' / 'game.html')
