"""update_job_enums

Revision ID: beed49420ecd
Revises: d563a53ac1cc
Create Date: 2025-06-06 22:16:25.855170

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'beed49420ecd'
down_revision = 'd563a53ac1cc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create all enum types
    jobtype = sa.Enum('delivery', 'pickup', 'task', name='jobtype')
    prioritylevel = sa.Enum('low', 'medium', 'high', name='prioritylevel')
    recurrencetype = sa.Enum('one_time', 'recurring', name='recurrencetype')
    paymentstatus = sa.Enum('paid', 'unpaid', name='paymentstatus')

    # Create enums in database
    for enum in [jobtype, prioritylevel, recurrencetype, paymentstatus]:
        enum.create(op.get_bind(), checkfirst=True)
    
    # Convert columns to use new enum types
    op.execute("ALTER TABLE jobs ALTER COLUMN job_type TYPE jobtype USING job_type::text::jobtype")
    op.execute("ALTER TABLE jobs ALTER COLUMN priority_level TYPE prioritylevel USING priority_level::text::prioritylevel")
    op.execute("ALTER TABLE jobs ALTER COLUMN recurrence_type TYPE recurrencetype USING recurrence_type::text::recurrencetype")
    op.execute("""
        ALTER TABLE jobs 
        ALTER COLUMN payment_status TYPE paymentstatus 
        USING CASE WHEN payment_status = true THEN 'paid'::paymentstatus 
                  ELSE 'unpaid'::paymentstatus 
             END
    """)

def downgrade() -> None:
    # Convert enum columns back to text/boolean
    op.execute("ALTER TABLE jobs ALTER COLUMN job_type TYPE varchar")
    op.execute("ALTER TABLE jobs ALTER COLUMN priority_level TYPE varchar")
    op.execute("ALTER TABLE jobs ALTER COLUMN recurrence_type TYPE varchar")
    op.execute("""
        ALTER TABLE jobs 
        ALTER COLUMN payment_status TYPE boolean 
        USING CASE WHEN payment_status = 'paid' THEN true 
                  ELSE false 
             END
    """)
    
    # Drop all enum types
    for enum in ['jobtype', 'prioritylevel', 'recurrencetype', 'paymentstatus']:
        op.execute(f"DROP TYPE IF EXISTS {enum}")
