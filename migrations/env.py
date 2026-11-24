import os

from alembic import context
from sqlalchemy import create_engine

from folio.db.models import Base

url = os.environ.get("DATABASE_URL") or context.config.get_main_option("sqlalchemy.url")
if not url:
    raise RuntimeError("DATABASE_URL is not set")

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(url).connect() as conn:
        context.configure(connection=conn, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
        conn.commit()
