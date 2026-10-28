from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
import math

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models import Character, CharacterLocation, InventoryItem, Item, Monster, WorldBoss, Battle, now
from backend.app.services import grant_item, stats, regenerate, InventoryService, add_xp
from backend.app.balance import simulate, item_power, regen_rate, level_start, level_for

@pytest.fixture(autouse=True)
def immediate_animation(monkeypatch):
    monkeypatch.setattr('backend.app.services.FRAME_SECONDS',0)

def fight(client,monster=1,key=None):
    return client.post('/api/battles',json={'monster_id':monster,'request_id':key or str(uuid4())})

def refill():
    with SessionLocal.begin() as db:
        c=db.scalar(select(Character));c.hp=c.max_hp;c.battle_until=None;c.hp_updated_at=now()

def test_registration_login_logout(client):
    assert client.get('/api/character').status_code==401
    payload={'username':'hero','password':'longpassword','name':'Герой'}
    assert client.post('/api/auth/register',json=payload).status_code==201
    assert client.get('/api/character').json()['attack']==6
    assert client.post('/api/auth/register',json=payload).status_code==409
    assert client.post('/api/auth/logout',json={}).status_code==200
    assert client.get('/api/character').status_code==401
    assert client.post('/api/auth/login',json={'username':'hero','password':'wrongpassword'}).status_code==401
    assert client.post('/api/auth/login',json=payload).status_code==200

def test_battle_retry_one_reward_persistent_hp(player):
    key=str(uuid4());first=fight(player,key=key)
    assert first.status_code==200 and first.json()['won']
    assert first.json()['final_hp']==42
    assert len(first.json()['frames'])==7
    assert fight(player,key=key).json()==first.json()
    assert player.get('/api/character').json()['xp']==30
    assert player.get('/api/character').json()['hp']==42
    assert fight(player,monster=2,key=key).status_code==409
    items=player.get('/api/inventory').json()
    assert next(i for i in items if i['item_id']==2)['quantity']==1

def test_no_click_cooldown(player):
    assert fight(player).status_code==200
    second=fight(player)
    assert second.status_code==200
    assert second.json()['final_hp']==24

def test_defeat_preserves_progress_and_zero_hp(player):
    first=fight(player).json();before=player.get('/api/inventory').json()
    lost=fight(player,7).json()
    assert not lost['won'] and lost['final_hp']==0
    assert player.get('/api/character').json()['hp']==0
    assert player.get('/api/character').json()['xp']==30
    assert player.get('/api/inventory').json()==before
    assert fight(player).status_code==400

def test_location_gated_by_miniboss_not_level(player):
    with SessionLocal.begin() as db:
        c=db.scalar(select(Character));c.level=50
    assert fight(player,3).status_code==403
    assert not player.get('/api/locations').json()[1]['unlocked']

def test_quest_claim_only_once(player):
    assert player.post('/api/quests/1/claim',json={}).status_code==400
    for _ in range(3):
        refill();assert fight(player).json()['won']
    assert player.post('/api/quests/1/claim',json={}).status_code==200
    assert player.post('/api/quests/1/claim',json={}).status_code==409
    assert player.get('/api/character').json()['xp']==150
    assert player.get('/api/character').json()['level']==1

def test_stack_merge_equipped_and_stats(player):
    with SessionLocal.begin() as db:
        c=db.scalar(select(Character));entry=grant_item(db,c,2,count=9);entry_id=entry.id
    assert player.post(f'/api/inventory/{entry_id}/equip',json={}).status_code==200
    assert player.get('/api/character').json()['attack']==12
    for _ in range(3):
        assert player.post(f'/api/inventory/{entry_id}/merge',json={}).status_code==200
    rows=player.get('/api/inventory').json();tier2=next(i for i in rows if i['item_id']==2)
    assert tier2['stars']==2 and tier2['quantity']==3 and tier2['equipped']
    assert player.post(f"/api/inventory/{tier2['id']}/merge",json={}).status_code==200
    rows=player.get('/api/inventory').json();tier3=next(i for i in rows if i['item_id']==2)
    assert tier3['stars']==3 and tier3['quantity']==1 and tier3['equipped']
    assert player.get('/api/character').json()['attack']==22
    assert player.post(f"/api/inventory/{tier3['id']}/merge",json={}).status_code==400

def test_five_star_cap_and_cross_item_isolation(player):
    with SessionLocal.begin() as db:
        c=db.scalar(select(Character));e=grant_item(db,c,2,stars=5,count=3);eid=e.id
        grant_item(db,c,3,count=2)
    assert player.post(f'/api/inventory/{eid}/merge',json={}).status_code==400
    assert len(player.get('/api/inventory').json())==3

def test_foreign_inventory_protected(player):
    eid=player.get('/api/inventory').json()[0]['id']
    with TestClient(app,base_url='https://testserver') as other:
        other.post('/api/auth/register',json={'username':'other','password':'longpassword','name':'Другой'})
        for endpoint in ['equip','unequip','merge']:
            assert other.post(f'/api/inventory/{eid}/{endpoint}',json={}).status_code==404

def test_no_health_or_damage_bonus_from_level(player):
    first=player.get('/api/character').json()
    with SessionLocal.begin() as db:
        c=db.scalar(select(Character));add_xp(c,level_start(10))
    second=player.get('/api/character').json()
    for key in ['max_hp','attack','defense']:
        assert second[key]==first[key]
    assert second['regen_percent']==1.9
    assert second['xp_next']==3000

@pytest.mark.parametrize('level',[1,2,3,10,100])
def test_xp_curve_ten_equal_tier_kills(level):
    start=level_start(level);threshold=300*level
    assert level_for(start)==level
    assert level_for(start+threshold-1)==level
    assert level_for(start+threshold)==level+1
    assert threshold/(30*level)==10

def test_offline_regen_and_no_regen_in_battle(player):
    with SessionLocal.begin() as db:
        c=db.scalar(select(Character));c.hp=0;c.hp_updated_at=now()-timedelta(seconds=100)
    assert player.get('/api/character').json()['hp']==6
    with SessionLocal.begin() as db:
        c=db.scalar(select(Character));c.hp=10;c.battle_until=now()+timedelta(seconds=30);c.hp_updated_at=now()-timedelta(hours=1)
    assert player.get('/api/character').json()['hp']==10
    assert player.get('/api/character').json()['in_battle']

def test_potions_outside_battle_only(player):
    with SessionLocal.begin() as db:
        c=db.scalar(select(Character));c.hp=0;c.potions=2;c.battle_until=now()+timedelta(seconds=30)
    assert player.post('/api/character/heal',json={}).status_code==409
    with SessionLocal.begin() as db:
        c=db.scalar(select(Character));c.battle_until=None;c.hp_updated_at=now()
    assert player.post('/api/character/heal',json={}).status_code==200
    h=player.get('/api/character').json();assert h['hp']==18 and h['potions']==1

def test_loot_potion_probability_branch_and_elixir_cap(player,monkeypatch):
    monkeypatch.setattr('backend.app.services.random.random',lambda:0.01)
    with SessionLocal.begin() as db:
        c=db.scalar(select(Character));p=db.scalar(select(CharacterLocation).where(CharacterLocation.location_id==1))
        p.next_elixir_at=1
    result=fight(player).json()
    h=player.get('/api/character').json();assert h['max_hp']==70 and h['potions']==1
    assert len(result['drops'])==3
    with SessionLocal.begin() as db:
        c=db.scalar(select(Character));c.hp=110;c.max_hp=110
        p=db.scalar(select(CharacterLocation).where(CharacterLocation.location_id==1));p.elixirs=5;p.next_elixir_at=0
    fight(player)
    assert player.get('/api/character').json()['max_hp']==110
    assert player.get('/api/locations').json()[0]['elixirs']==5

def test_no_potion_drop(player,monkeypatch):
    monkeypatch.setattr('backend.app.services.random.random',lambda:0.99)
    fight(player)
    assert player.get('/api/character').json()['potions']==0
    assert len(player.get('/api/inventory').json())==2

@pytest.mark.parametrize('stage,weapon,armor,hp',[(1,2,3,100),(2,4,5,140),(3,6,7,180)])
def test_miniboss_balance_required_elixirs(player,stage,weapon,armor,hp):
    with SessionLocal.begin() as db:
        c=db.scalar(select(Character))
        a=4+item_power(db.get(Item,weapon).attack,3);d=item_power(db.get(Item,armor).defense,3)
        m=db.get(Monster,stage+6)
        _,remaining,enemy=simulate(hp,m.hp,a,d,m.attack)
        assert remaining>0 and enemy==0
        _,remaining,enemy=simulate(hp-10,m.hp,a,d,m.attack)
        assert remaining==0 and enemy>0
        for e in db.scalars(select(InventoryItem)):e.equipped=False
        grant_item(db,c,weapon,stars=3).equipped=True
        grant_item(db,c,armor,stars=3).equipped=True
        c.hp=hp;c.max_hp=hp
        for p in db.scalars(select(CharacterLocation)):
            if p.location_id<stage:p.miniboss_defeated=True
    result=fight(player,stage+6)
    assert result.status_code==200 and result.json()['won']
    locs=player.get('/api/locations').json();assert locs[stage-1]['cleared']
    if stage<3:assert locs[stage]['unlocked']
    assert fight(player,stage+6).status_code==409

def test_boss_counterattack_and_retry(player):
    key=str(uuid4());r=player.post('/api/boss/attack',json={'request_id':key})
    assert r.status_code==200
    assert r.json()['final_hp']==36 and r.json()['damage']==6
    assert len(r.json()['frames'])==2
    assert player.post('/api/boss/attack',json={'request_id':key}).json()==r.json()
    assert player.get('/api/boss').json()['hp']==4994

def test_parallel_boss_no_lost_damage(player):
    with TestClient(app,base_url='https://testserver') as other:
        other.post('/api/auth/register',json={'username':'other','password':'longpassword','name':'Другой'})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=[f.result() for f in [pool.submit(c.post,'/api/boss/attack',json={'request_id':str(uuid4())}) for c in [player,other]]]
        assert all(r.status_code==200 for r in results)
        assert player.get('/api/boss').json()['hp']==5000-sum(r.json()['damage'] for r in results)

def test_parallel_duplicate_battle(player):
    key=str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:fight(player,key=key),range(2)))
    assert results[0].json()==results[1].json()
    assert player.get('/api/character').json()['xp']==30

def test_boss_variants_and_no_retaliation_when_dead(player):
    for variant in [1,2,0]:
        with SessionLocal.begin() as db:
            boss=db.scalar(select(WorldBoss).order_by(WorldBoss.id.desc()));boss.hp=1
        r=player.post('/api/boss/attack',json={'request_id':str(uuid4())}).json()
        assert r['damage']==1 and len(r['frames'])==1
        with SessionLocal.begin() as db:
            boss=db.scalar(select(WorldBoss).order_by(WorldBoss.id.desc()));boss.defeated_at=now()-timedelta(seconds=61)
        b=player.get('/api/boss').json();assert b['hp']==5000 and b['variant']==variant

def test_active_animation_blocks_heal_equipment_other_fight(player,monkeypatch):
    monkeypatch.setattr('backend.app.services.FRAME_SECONDS',10)
    r=fight(player)
    assert r.status_code==200
    assert player.get('/api/character').json()['in_battle']
    assert fight(player).status_code==409
    assert player.post('/api/character/heal',json={}).status_code==409
    item=player.get('/api/inventory').json()[0]['id']
    assert player.post(f'/api/inventory/{item}/unequip',json={}).status_code==409
    history=player.get('/api/battles').json();assert history[0]['result']==r.json()

def test_chat_security_and_validation(player):
    assert player.post('/api/chat',json={'text':'   '}).status_code==422
    assert player.post('/api/chat',json={'text':'x'*301}).status_code==422
    assert player.post('/api/chat',json={'text':'Привет'}).status_code==201
    assert player.get('/api/chat').json()[0]['text']=='Привет'
    assert player.post('/api/chat',json={'text':'test'},headers={'Origin':'https://evil.example'}).status_code==403
    assert player.post('/api/battles',json={'monster_id':1,'request_id':'bad'}).status_code==422

def test_progress_survives_new_session(player):
    fight(player)
    with TestClient(app,base_url='https://testserver') as fresh:
        fresh.post('/api/auth/login',json={'username':'tester','password':'testpassword123'})
        h=fresh.get('/api/character').json();assert h['xp']==30 and h['hp']==42
        assert len(fresh.get('/api/battles').json())==1

def test_static_and_health(client):
    for path in ['/','/game','/static/css/style.css','/static/js/game.js','/docs','/openapi.json']:
        assert client.get(path).status_code==200
    assert client.get('/health').json()['database']=='postgresql'

def test_complete_three_location_journey(player,monkeypatch):
    monkeypatch.setattr('backend.app.services.random.randint',lambda a,b:4 if a==3 else 8)
    with SessionLocal.begin() as db:
        for p in db.scalars(select(CharacterLocation)):p.next_elixir_at=4
    for stage in range(1,4):
        for monster in [stage*2-1,stage*2]:
            for _ in range(9):
                refill()
                result=fight(player,monster)
                assert result.status_code==200 and result.json()['won']
        # 9 copies per slot -> 3 two-star -> 1 three-star.
        for item_id in [stage*2,stage*2+1]:
            rows=player.get('/api/inventory').json()
            entry=next(i for i in rows if i['item_id']==item_id and i['stars']==1)
            assert entry['quantity']==9
            for _ in range(3):
                assert player.post(f"/api/inventory/{entry['id']}/merge",json={}).status_code==200
            entry=next(i for i in player.get('/api/inventory').json() if i['item_id']==item_id and i['stars']==2)
            assert player.post(f"/api/inventory/{entry['id']}/merge",json={}).status_code==200
            entry=next(i for i in player.get('/api/inventory').json() if i['item_id']==item_id and i['stars']==3)
            assert player.post(f"/api/inventory/{entry['id']}/equip",json={}).status_code==200
        assert player.get('/api/character').json()['max_hp']==60+40*stage
        assert player.get('/api/locations').json()[stage-1]['elixirs']==4
        refill()
        result=fight(player,6+stage).json()
        assert result['won'] and result['final_hp'] in [4,5]


def test_next_location_item_matches_previous_two_stars(player):
    with SessionLocal() as db:
        for old,new in [(2,4),(3,5),(4,6),(5,7)]:
            a,b=db.get(Item,old),db.get(Item,new)
            assert item_power(a.attack or a.defense,2)==(b.attack or b.defense)

def test_login_rate_limit_does_not_limit_gameplay(player):
    payload={'username':'tester','password':'wrongpassword'}
    for _ in range(12):
        assert player.post('/api/auth/login',json=payload).status_code==401
    limited=player.post('/api/auth/login',json=payload)
    assert limited.status_code==429 and limited.headers['Retry-After']=='60'
    assert fight(player).status_code==200
