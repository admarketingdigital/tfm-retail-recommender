from fastapi import APIRouter, HTTPException, Query, Depends
from app.dao.products import ProductsDAO
from app.services import auth
from typing import Literal
from app.services import annoy_index

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/single/{product_id}")
def get_product(product_id: str, user: dict = Depends(auth.get_current_user)):
    try:
        data = ProductsDAO.get_by_id(product_id)
    except NotImplementedError as e:
        # No insertamos ni creamos tablas → indicamos que no está disponible
        raise HTTPException(status_code=501, detail=str(e))
    if not data:
        raise HTTPException(status_code=404, detail="product_not_found")
    return data



@router.get("/filter")
def get_filter_products(
    gender: str | None = None,
    mastercategory: str | None = None,
    subcategory: str | None = None,
    articletype: str | None = None,
    basecolour: str | None = None,
    season: str | None = None,
    year: int | None = None,
    usage: str | None = None,
    limit: int = Query(10, ge=1, le=200), 
    user: dict = Depends(auth.get_current_user)
):
    print("gender: ",gender)
    try:
        data = ProductsDAO.filter_products(
            gender=gender,
            mastercategory=mastercategory,
            subcategory=subcategory,
            articletype=articletype,
            basecolour=basecolour,
            season=season,
            year=year,
            usage=usage,
            limit=limit
        )
        return data
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/values/{column}")
def get_distinct_values(
    column: Literal[
        "gender",
        "mastercategory",
        "subcategory",
        "articletype",
        "basecolour",
        "season",
        "year",
        "usage",
    ], user: dict = Depends(auth.get_current_user)
):
    """
    Devuelve los valores distintos para una de las columnas permitidas.
    """
    try:
        values = ProductsDAO.get_distinct_values(column)
        return {"column": column, "values": values}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/similar/{product_id}")
def get_similar_products(product_id: int, n: int = Query(10, ge=1, le=50), user: dict = Depends(auth.get_current_user)):
    try:
        # ✅ El índice ya está cargado en memoria en `on_startup`
        if product_id not in annoy_index.REVERSE_ID_MAP:
            raise HTTPException(status_code=404, detail="product_not_found")

        base_idx = annoy_index.REVERSE_ID_MAP[product_id]
        neighbors, distances = annoy_index.INDEX.get_nns_by_item(base_idx, n+1, include_distances=True)

        # Eliminar el propio producto
        neighbors, distances = neighbors[1:], distances[1:]

        results = []
        for idx, dist in zip(neighbors, distances):
            pid = annoy_index.PRODUCT_ID_MAP[idx]
            meta = annoy_index.PRODUCT_METADATA.get(str(pid), {})
            results.append({
                "product_id": pid,
                "name": meta.get("name"),
                "image_url": meta.get("image_url"),
                "score": round(1 - dist, 4)
            })

        return {
            "base_product": {
                "product_id": product_id,
                "name": annoy_index.PRODUCT_METADATA.get(str(product_id), {}).get("name"),
                "image_url": annoy_index.PRODUCT_METADATA.get(str(product_id), {}).get("image_url"),
            },
            "neighbors": results
        }
    except HTTPException:
        raise  # deja pasar los 404 correctamente
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))