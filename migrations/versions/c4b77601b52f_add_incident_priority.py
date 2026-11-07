"""Initial schema + incident priority

Revision ID: c4b77601b52f
Revises:
Create Date: 2026-11-06 21:20:16.131916

This revision works on three kinds of database:
  * a brand-new empty database (creates every table),
  * a database made by db.create_all() without Alembic (only stamps/adds what is missing),
  * the older database that lacked incidents.priority (adds the column safely).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4b77601b52f'
down_revision = None
branch_labels = None
depends_on = None


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade():
    existing = _tables()

    if 'users' not in existing:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('email', sa.String(length=150), nullable=False),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('role', sa.String(length=30), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_users_email', 'users', ['email'], unique=True)

    if 'incidents' not in existing:
        op.create_table(
            'incidents',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('service_name', sa.String(length=120), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('severity', sa.String(length=30), nullable=False),
            sa.Column('priority', sa.String(length=20), nullable=False),
            sa.Column('status', sa.String(length=30), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('system_logs', sa.Text(), nullable=True),
            sa.Column('assigned_engineer_id', sa.Integer(), nullable=True),
            sa.Column('verified_root_cause', sa.Text(), nullable=True),
            sa.Column('resolution_summary', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('resolved_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['assigned_engineer_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        for col in ('service_name', 'severity', 'priority', 'status',
                    'assigned_engineer_id', 'created_at'):
            op.create_index('ix_incidents_' + col, 'incidents', [col], unique=False)
    else:
        columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('incidents')]
        if 'priority' not in columns:
            with op.batch_alter_table('incidents', schema=None) as batch_op:
                batch_op.add_column(sa.Column(
                    'priority', sa.String(length=20), nullable=False,
                    server_default='medium'))
                batch_op.create_index(
                    batch_op.f('ix_incidents_priority'), ['priority'], unique=False)

    if 'incident_actions' not in existing:
        op.create_table(
            'incident_actions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('incident_id', sa.Integer(), nullable=False),
            sa.Column('engineer_id', sa.Integer(), nullable=True),
            sa.Column('action_description', sa.Text(), nullable=False),
            sa.Column('outcome', sa.String(length=30), nullable=False),
            sa.Column('actual_result', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['engineer_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_incident_actions_incident_id', 'incident_actions',
                        ['incident_id'], unique=False)

    if 'incident_logs' not in existing:
        op.create_table(
            'incident_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('incident_id', sa.Integer(), nullable=False),
            sa.Column('log_message', sa.Text(), nullable=False),
            sa.Column('log_level', sa.String(length=20), nullable=True),
            sa.Column('timestamp', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_incident_logs_incident_id', 'incident_logs',
                        ['incident_id'], unique=False)
        op.create_index('ix_incident_logs_timestamp', 'incident_logs',
                        ['timestamp'], unique=False)

    if 'handovers' not in existing:
        op.create_table(
            'handovers',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('outgoing_engineer_id', sa.Integer(), nullable=True),
            sa.Column('incoming_engineer_id', sa.Integer(), nullable=True),
            sa.Column('shift_start', sa.DateTime(), nullable=True),
            sa.Column('shift_end', sa.DateTime(), nullable=True),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('active_incidents', sa.JSON(), nullable=True),
            sa.Column('resolved_incidents', sa.JSON(), nullable=True),
            sa.Column('successful_actions', sa.JSON(), nullable=True),
            sa.Column('failed_actions', sa.JSON(), nullable=True),
            sa.Column('verified_findings', sa.JSON(), nullable=True),
            sa.Column('pending_tasks', sa.JSON(), nullable=True),
            sa.Column('recommendations', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['incoming_engineer_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['outgoing_engineer_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'chat_sessions' not in existing:
        op.create_table(
            'chat_sessions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_chat_sessions_user_id', 'chat_sessions', ['user_id'], unique=False)

    if 'chat_messages' not in existing:
        op.create_table(
            'chat_messages',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('session_id', sa.Integer(), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('response', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_chat_messages_session_id', 'chat_messages',
                        ['session_id'], unique=False)


def downgrade():
    # Dropping the whole schema is destructive, so only the priority column is reverted.
    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_incidents_priority'))
        batch_op.drop_column('priority')
