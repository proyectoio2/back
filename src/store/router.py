from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from src.store import service, schemas
from src.auth.service import get_current_user
from src.database import get_db

router = APIRouter(prefix="/store", tags=["store"])

@router.get("/products", response_model=List[schemas.Product])
def list_products(db: Session = Depends(get_db)):
    return service.get_products(db)

@router.get("/products/{product_id}", response_model=schemas.Product)
def get_product(product_id: UUID, db: Session = Depends(get_db)):
    product = service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product

@router.post("/products", response_model=schemas.Product, status_code=status.HTTP_201_CREATED)
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="No autorizado")
    return service.create_product(db, product)

@router.get("/cart", response_model=schemas.Cart)
def get_cart(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    cart = service.get_cart(db, current_user.id)
    if not cart:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    return cart

@router.post("/cart/add", response_model=schemas.Cart)
def add_to_cart(request: schemas.AddToCartRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return service.add_to_cart(db, current_user, request.product_id, request.quantity)

@router.post("/cart/checkout", response_model=schemas.Order)
def checkout(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return service.checkout_cart(db, current_user)

@router.get("/reports/sales", response_model=schemas.SalesReportResponse)
def sales_report(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    report = service.get_sales_report(db, current_user)
    return report 