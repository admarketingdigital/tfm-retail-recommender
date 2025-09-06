from fastapi import APIRouter, HTTPException, Depends
from app.dao.customers import CustomersDAO
from app.services import auth

router = APIRouter(prefix="/customers", tags=["Customers"])

@router.get("/{customer_id}", summary="Obtener un cliente por ID", description="Devuelve la información detallada de un cliente y un producto aleatorio de los que ha comprado o visualizado.")
def get_customer(customer_id: str, user: dict = Depends(auth.get_current_user)):
    try:
        data = CustomersDAO.get_customer_with_products(customer_id)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    if not data:
        raise HTTPException(status_code=404, detail="customer_not_found")
    return data