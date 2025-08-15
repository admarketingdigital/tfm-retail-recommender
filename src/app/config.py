import os
from dotenv import load_dotenv

# Cargar las variables del archivo .env
load_dotenv()

# Tokens de API
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_PRODUCTS_LLM")
OPENAI_API_KEY = os.getenv("TELEGRAM_BOT_TOKEN_PRODUCTS_CHATGPT")

# Parámetros de conexión a la base de datos
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Validaciones
assert TELEGRAM_BOT_TOKEN, "⚠️ Falta TELEGRAM_BOT_TOKEN_PRODUCTS_LLM en .env"
assert OPENAI_API_KEY, "⚠️ Falta TELEGRAM_BOT_TOKEN_PRODUCTS_CHATGPT en .env"
assert DB_HOST and DB_PORT and DB_NAME and DB_USER and DB_PASSWORD, "⚠️ Faltan variables de conexión a PostgreSQL"
