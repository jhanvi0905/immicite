from alembic import context
from sqlalchemy import create_engine

from app.config import Settings

# Migrations are hand-written SQL, so there is no metadata to autogenerate from.
target_metadata = None


def run_migrations() -> None:
    url = context.config.get_main_option("sqlalchemy.url") or Settings().database_url
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
