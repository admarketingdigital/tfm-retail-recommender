from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from app.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

# Crear engine de SQLAlchemy reutilizable
engine = create_engine(
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    poolclass=NullPool,
    connect_args={"connect_timeout": 120}
)