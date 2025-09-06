# app/core/config.py
import os
from pydantic import BaseModel
from dotenv import load_dotenv

# Carga .env desde la raíz del proyecto
load_dotenv()

class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "TFM Retail Recommender API")
    app_env: str = os.getenv("APP_ENV", "local")

    # Cache
    cache_backend: str = os.getenv("CACHE_BACKEND", "memory").lower()  # memory | redis
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "900"))

    # Redis
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))


    # PostgreSQL
    pg_host: str = os.getenv("POSTGRES_HOST", "localhost")
    pg_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    pg_db: str = os.getenv("POSTGRES_DB", "tfm")
    pg_user: str = os.getenv("POSTGRES_USER", "tfm")
    pg_password: str = os.getenv("POSTGRES_PASSWORD", "changeme")
    db_required_for_tests: int = int(os.getenv("DB_REQUIRED_FOR_TESTS", "0"))
    products_required_for_tests: int = int(os.getenv("PRODUCTS_REQUIRED_FOR_TESTS", "0"))

    product_table: str = os.getenv("PRODUCT_TABLE", "products")
    product_id_col: str = os.getenv("PRODUCT_ID_COLUMN", "product_id")
    product_name_col: str = os.getenv("PRODUCT_NAME_COLUMN", "name")
    product_category_col: str = os.getenv("PRODUCT_CATEGORY_COLUMN", "category")
    product_image_url: str = os.getenv("PRODUCT_IMAGE_URL", "image_url")

    customer_table: str = os.getenv("CUSTOMER_TABLE", "products")
    customer_id_col: str = os.getenv("CUSTOMER_ID_COLUMN", "product_id")
    customer_name_col: str = os.getenv("CUSTOMER_NAME_COLUMN", "name")
    customer_last_name_col: str = os.getenv("CUSTOMER_LAST_NAME_COLUMN", "category")

    jwt_user: str = os.getenv("JWT_USER","admin")
    jwt_password: str = os.getenv("JWT_PASSWORD","1234")
    
settings = Settings()
