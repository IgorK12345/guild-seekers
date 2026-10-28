"""Combat, equipment stacks and health. Authorized one-time progress reset.

Accounts and password hashes remain intact. Previous progress is backed up
separately before applying this migration to the local project.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a21028_combat_progression'
down_revision = '8fab60b6cfea'
branch_labels = None
depends_on = None

def upgrade():
    op.execute('DELETE FROM battles')
    op.execute('DELETE FROM inventory_items')
    op.execute('DELETE FROM world_bosses')
    op.execute('UPDATE character_quests SET progress=0, claimed=false')
    op.execute('UPDATE characters SET xp=0, level=1, last_action=NULL')
    for name, type_, default in [
        ('hp',sa.Float(),'60'),('max_hp',sa.Integer(),'60'),('potions',sa.Integer(),'0'),
        ('hp_updated_at',sa.DateTime(timezone=True),'CURRENT_TIMESTAMP')]:
        op.add_column('characters',sa.Column(name,type_,nullable=False,server_default=sa.text(default)))
    op.add_column('characters',sa.Column('battle_until',sa.DateTime(timezone=True),nullable=True))
    op.create_check_constraint('ck_character_health','characters','hp >= 0 AND hp <= max_hp AND max_hp >= 60 AND potions >= 0')
    op.add_column('monsters',sa.Column('is_miniboss',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('inventory_items',sa.Column('stars',sa.Integer(),nullable=False,server_default='1'))
    op.add_column('inventory_items',sa.Column('quantity',sa.Integer(),nullable=False,server_default='1'))
    op.create_unique_constraint('uq_inventory_stack','inventory_items',['character_id','item_id','stars'])
    op.create_check_constraint('ck_inventory_stack','inventory_items','stars BETWEEN 1 AND 5 AND quantity > 0')
    op.execute('INSERT INTO inventory_items(character_id,item_id,equipped,stars,quantity) SELECT id,1,true,1,1 FROM characters')
    op.create_table('character_locations',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('character_id',sa.Integer(),sa.ForeignKey('characters.id'),nullable=False),
        sa.Column('location_id',sa.Integer(),sa.ForeignKey('locations.id'),nullable=False),
        sa.Column('kills',sa.Integer(),nullable=False),
        sa.Column('elixirs',sa.Integer(),nullable=False),
        sa.Column('next_elixir_at',sa.Integer(),nullable=False),
        sa.Column('miniboss_defeated',sa.Boolean(),nullable=False),
        sa.UniqueConstraint('character_id','location_id'),
        sa.CheckConstraint('elixirs BETWEEN 0 AND 5 AND kills >= 0'))
    op.add_column('world_bosses',sa.Column('variant',sa.Integer(),nullable=False,server_default='0'))
    op.add_column('world_bosses',sa.Column('attack',sa.Integer(),nullable=False,server_default='24'))
    op.add_column('world_bosses',sa.Column('icon',sa.String(20),nullable=False,server_default='🐉'))

def downgrade():
    raise RuntimeError('Restore the pre-upgrade backup to recover previous game progress.')
