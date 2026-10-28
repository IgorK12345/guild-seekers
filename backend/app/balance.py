"""Adjustable progression values. Levels only affect passive healing."""
import math

BASE_HP = 60
BASE_ATTACK = 4
ELIXIR_HP = 10
POTION_CHANCE = 0.15
POTION_HEAL = 0.30
FRAME_SECONDS = 0.45
STAR_MULTIPLIERS = (1, 1.5, 2.25, 3.375, 5.0625)
BOSSES = (
    dict(name='Эребус, древний дракон', attack=24, icon='🐉'),
    dict(name='Морозный исполин', attack=32, icon='🧊'),
    dict(name='Владыка пепла', attack=40, icon='👹'),
)

def item_power(value, stars):
    return int(math.floor(value * STAR_MULTIPLIERS[stars - 1] + 0.5))

def level_start(level):
    return 150 * (level - 1) * level

def level_for(xp):
    return (1 + math.isqrt(1 + 4 * (xp // 150))) // 2

def regen_rate(level, max_hp):
    return max_hp * 0.001 * (1 + 0.1 * (level - 1))

def simulate(hero_hp, enemy_hp, attack, defense, enemy_attack, enemy_defense=0, single_exchange=False):
    """Alternating attacks, with no arbitrary round cutoff."""
    frames = []
    while hero_hp > 0 and enemy_hp > 0:
        damage = min(enemy_hp, max(1, attack - enemy_defense))
        enemy_hp -= damage
        frames.append(dict(actor='hero', damage=damage, hero_hp=hero_hp, enemy_hp=enemy_hp))
        if enemy_hp <= 0:
            break
        damage = min(hero_hp, max(1, enemy_attack - defense))
        hero_hp -= damage
        frames.append(dict(actor='enemy', damage=damage, hero_hp=hero_hp, enemy_hp=enemy_hp))
        if single_exchange:
            break
    return frames, hero_hp, enemy_hp
