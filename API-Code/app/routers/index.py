from fastapi import APIRouter, HTTPException
from app.adapters.db import ping
from app.services import annoy_index

router = APIRouter(tags=["System"])

@router.get("/info")
def info():
    return {"name": "TFM Retail Recommender API", "version": "0.1.0"}

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/db/health")
def db_health():
    if not ping():
        raise HTTPException(status_code=500, detail="db_down")
    return {"status": "ok"}


@router.get("/index/health")
def index_health():
    try:
        if annoy_index.INDEX is None:
            raise HTTPException(status_code=500, detail="index_not_loaded")

        return {
            "status": "ok",
            "num_products": len(annoy_index.PRODUCT_METADATA),
            "dim": annoy_index.INDEX_DIM
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))