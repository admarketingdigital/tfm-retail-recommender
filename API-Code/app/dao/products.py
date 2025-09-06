# app/dao/products.py
from typing import List, Dict, Any, Optional
from psycopg2.extras import RealDictCursor
from app.adapters.db import get_conn, table_exists
from app.core.config import settings

class ProductsDAO:
    @staticmethod
    def ensure_table_available() -> None:
        if not table_exists("public", settings.product_table):
            # No creamos nada; devolvemos señal de NO implementado
            raise NotImplementedError(f"Tabla no disponible: public.{settings.product_table}")

    @staticmethod
    def get_by_id(product_id: str) -> Optional[Dict[str, Any]]:
        ProductsDAO.ensure_table_available()
        q = f"""
            SELECT 
              {settings.product_id_col} AS product_id,
              {settings.product_name_col} AS name,
              {settings.product_category_col} AS category,
              {settings.product_image_url} AS image_url
            FROM public.{settings.product_table}
            WHERE {settings.product_id_col}::text = %s
            LIMIT 1;
        """
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(q, (product_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    @staticmethod
    def filter_products(
        gender: Optional[str] = None,
        mastercategory: Optional[str] = None,
        subcategory: Optional[str] = None,
        articletype: Optional[str] = None,
        basecolour: Optional[str] = None,
        season: Optional[str] = None,
        year: Optional[int] = None,
        usage: Optional[str] = None,
        limit: int = 10  # por defecto 10
    ) -> List[Dict[str, Any]]:
        ProductsDAO.ensure_table_available()

        # 👮 limitar el parámetro máximo a 10
        if not limit or limit > 10:
            limit = 10
        
        filters = []
        params = []
    
        if gender:
            filters.append("LOWER(gender) = LOWER(%s)")
            params.append(gender)
        if mastercategory:
            filters.append("LOWER(mastercategory) = LOWER(%s)")
            params.append(mastercategory)
        if subcategory:
            filters.append("LOWER(subcategory) = LOWER(%s)")
            params.append(subcategory)
        if articletype:
            filters.append("LOWER(articletype) = LOWER(%s)")
            params.append(articletype)
        if basecolour:
            filters.append("LOWER(basecolour) = LOWER(%s)")
            params.append(basecolour)
        if season:
            filters.append("LOWER(season) = LOWER(%s)")
            params.append(season)
        if year:
            filters.append("year = %s")
            params.append(year)
        if usage:
            filters.append("LOWER(usage) = LOWER(%s)")
            params.append(usage)
    
        where_clause = " AND ".join(filters) if filters else "TRUE"
    
        q = f"""
            SELECT 
              {settings.product_id_col} AS product_id,
              {settings.product_name_col} AS name,
              {settings.product_category_col} AS category,
              {settings.product_image_url} AS image_url,
              gender, mastercategory, subcategory, articletype,
              basecolour, season, year, usage
            FROM public.{settings.product_table}
            WHERE {where_clause}
            ORDER BY RANDOM()
            LIMIT %s;
        """
        params.append(limit)
    
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(q, tuple(params))
                rows = cur.fetchall()
                return [dict(r) for r in rows]  # lista, como mucho `limit` elementos


    @staticmethod
    def get_distinct_values(column: str) -> List[str]:
        """
        Devuelve los valores distintos de una columna permitida.
        """
        allowed_columns = [
            "gender",
            "mastercategory",
            "subcategory",
            "articletype",
            "basecolour",
            "season",
            "year",
            "usage",
        ]

        if column not in allowed_columns:
            raise ValueError(f"Columna no permitida: {column}")

        ProductsDAO.ensure_table_available()

        q = f"""
            SELECT DISTINCT {column}
            FROM public.{settings.product_table}
            WHERE {column} IS NOT NULL
            ORDER BY {column};
        """

        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(q)
                rows = cur.fetchall()
                return [r[column] for r in rows if r[column] is not None]
