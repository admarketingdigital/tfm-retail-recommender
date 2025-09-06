from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.services import annoy_index
from app.routers import products, customers, index, auth
from mangum import Mangum   # 👈 Importar Mangum

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🚀 Cargar Annoy al arranque
    try:
        annoy_index.load_index()
        print("✅ Annoy index cargado en el arranque")
    except Exception as e:
        print(f"⚠️ No se pudo cargar el índice Annoy en startup: {e}")
    yield
    # 👇 aquí podrías añadir lógica de cierre si la necesitaras
    # ej: cerrar conexiones, limpiar recursos, etc.

app = FastAPI(
    title="TFM Retail Recommender API",
    version="0.1.0",
    description="""
### Trabajo Fin de Máster – UAH

Esta API expone:

- **Gestión de productos** (`/v1/products/single/{product_id}`)
- **Gestión de clientes** (`/v1/customers/{customers_id}`)
- **Filtros de productos** (`/v1/procutcs/filter`)
- **Recomendaciones con Annoy** (`/v1/products/similar/{product_id}`)
- **Autenticación JWT** (`/v1/auth/token`)

La API está protegida con **JWT**. Primero obtén un token en `/v1/auth/token`, luego usa **Authorize** en la esquina superior derecha para añadirlo.
    """,
    contact={
        "name": "Grupo 3 - Máster en Analítica de Datos en Marketing Digital",
        "email": "grupo3@example.com",
    },
    license_info={
        "name": "MIT License",
    },
    lifespan=lifespan,  # 👈 esto enlaza el hook de startup/shutdown
)

app.include_router(auth.router, prefix="/v1")
app.include_router(products.router, prefix="/v1")
app.include_router(customers.router, prefix="/v1")
app.include_router(index.router, prefix="/v1")

# 👇 Handler para Lambda (API Gateway → Lambda → FastAPI)
handler = Mangum(app)