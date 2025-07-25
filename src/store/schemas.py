from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

class ProductBase(BaseModel):
    image_url: str
    title: str
    description: str
    price: float
    stock: int

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    class Config:
        from_attributes = True

class CartProductBase(BaseModel):
    product_id: UUID
    quantity: int

class CartProduct(CartProductBase):
    id: UUID
    product: Product
    class Config:
        from_attributes = True

class Cart(BaseModel):
    id: UUID
    user_id: UUID
    cart_products: List[CartProduct]
    created_at: datetime
    updated_at: Optional[datetime]
    class Config:
        from_attributes = True

class AddToCartRequest(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)

class UpdateCartItemRequest(BaseModel):
    product_id: UUID
    quantity: int = Field(ge=0)  # ge=0 permite eliminar (quantity=0)

class RemoveFromCartRequest(BaseModel):
    product_id: UUID

class OrderProduct(BaseModel):
    id: UUID
    product: Product
    quantity: int
    price: float
    class Config:
        from_attributes = True

class Order(BaseModel):
    id: UUID
    order_number: str
    user_id: UUID
    full_name: str
    phone_number: str
    address: str
    total: float
    created_at: datetime
    status: str
    order_products: List[OrderProduct]
    class Config:
        from_attributes = True

class CheckoutResponse(BaseModel):
    order_number: str
    full_name: str
    phone_number: str
    address: str
    order: List[OrderProduct]
    total: float

class SalesReport(BaseModel):
    date: str
    total_sales: float
    total_orders: int
    products: Optional[List[Product]] = None 

class ProductSalesSummary(BaseModel):
    product_id: UUID
    title: str
    units_sold: int
    total: float

class SaleDetail(BaseModel):
    order_id: UUID
    order_number: str
    customer_name: str
    customer_email: str
    customer_phone: str
    purchase_date: datetime
    purchase_time: str
    total_amount: float
    products: list[dict]  # Lista de productos con cantidad y precio

class DailySalesReport(BaseModel):
    date: str
    total_sales: float
    total_orders: int
    products: list[ProductSalesSummary]
    sales_details: list[SaleDetail]  # Detalles de cada venta del día

class WeeklySalesReport(BaseModel):
    week: str
    total_sales: float
    total_orders: int
    products: list[ProductSalesSummary]
    sales_details: list[SaleDetail]  # Detalles de cada venta de la semana

class SalesReportResponse(BaseModel):
    daily_sales: list[DailySalesReport]
    weekly_sales: list[WeeklySalesReport]
    product_summary: list[ProductSalesSummary]
    all_sales_details: list[SaleDetail]  # Todas las ventas detalladas 