"""TimescaleDB hypertable for sensor history (PostgreSQL deployment only)."""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
        op.execute("SELECT create_hypertable('sensor_readings', 'observed_at', if_not_exists => TRUE, migrate_data => TRUE)")
        # No automatic delete policy before raw archive + retention approval.


def downgrade():
    raise RuntimeError("Hypertable/history rollback memerlukan restore tervalidasi.")
