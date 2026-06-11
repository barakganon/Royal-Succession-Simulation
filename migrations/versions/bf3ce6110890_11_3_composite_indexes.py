"""11-3 composite indexes

Revision ID: bf3ce6110890
Revises: f0fef8e6007c
Create Date: 2026-06-11 22:38:15.793516

Adds two composite indexes for hot read paths (Story 11-3):
  - ix_history_dynasty_year: history_log_entry(dynasty_id, year) — filter+sort
  - ix_project_dynasty_status_completion: project(dynasty_id, status, completion_year)

Autogen-detected FK/db_version/nullability changes were stripped: they are SQLite
cycle-introspection noise and pre-existing live-DB drift, not part of this story.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'bf3ce6110890'
down_revision = 'f0fef8e6007c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('history_log_entry', schema=None) as batch_op:
        batch_op.create_index('ix_history_dynasty_year', ['dynasty_id', 'year'], unique=False)

    with op.batch_alter_table('project', schema=None) as batch_op:
        batch_op.create_index('ix_project_dynasty_status_completion', ['dynasty_id', 'status', 'completion_year'], unique=False)


def downgrade():
    with op.batch_alter_table('project', schema=None) as batch_op:
        batch_op.drop_index('ix_project_dynasty_status_completion')

    with op.batch_alter_table('history_log_entry', schema=None) as batch_op:
        batch_op.drop_index('ix_history_dynasty_year')
