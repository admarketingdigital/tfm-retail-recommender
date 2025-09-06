# app/dao/customers.py
from typing import Optional, Dict, Any, List
from psycopg2.extras import RealDictCursor
from app.adapters.db import get_conn, table_exists
from app.core.config import settings


class CustomersDAO:
    @staticmethod
    def ensure_table_available() -> None:
        if not table_exists("public", settings.customer_table):
            raise NotImplementedError(f"Tabla no disponible: public.{settings.customer_table}")

    @staticmethod
    def get_customer_with_products(customer_id: str) -> Optional[Dict[str, Any]]:
        CustomersDAO.ensure_table_available()

        q_customer = f"""
            SELECT {settings.customer_name_col} AS first_name, 
           {settings.customer_last_name_col} AS last_name
            FROM {settings.customer_table}
            WHERE {settings.customer_id_col}::text = %s
            LIMIT 1;
        """

        q_products = F"""
            SELECT pem.product_id,
                   p.{settings.product_name_col} AS name,
                   p.{settings.product_image_url}
            FROM {settings.customer_table} c
            JOIN transactions t ON c.{settings.customer_id_col}= t.{settings.customer_id_col}
            JOIN click_stream cs ON t.session_id = cs.session_id
            JOIN product_event_metadata pem ON cs.event_id = pem.event_id
            JOIN {settings.product_table} p ON pem.product_id = p.{settings.product_id_col}
            WHERE c.{settings.customer_id_col} = %s
            ORDER BY RANDOM()
            LIMIT 1;
        """

        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Datos del cliente
                cur.execute(q_customer, (customer_id,))
                row = cur.fetchone()
                if not row:
                    return None

                customer = dict(row)

                # Productos asociados
                cur.execute(q_products, (customer_id,))
                products = [dict(r) for r in cur.fetchall()]

                return {
                    "customer_id": customer_id,
                    "first_name": customer["first_name"],
                    "last_name": customer["last_name"],
                    "products": products,
                }
