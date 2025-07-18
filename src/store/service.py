from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import UUID
from datetime import datetime, timedelta
from src.store import models, schemas
from src.auth.models import User
import random
import string
from sqlalchemy import func

def get_products(db: Session):
    return db.query(models.Product).filter(models.Product.is_active == True).all()

def get_product(db: Session, product_id: UUID):
    return db.query(models.Product).filter(models.Product.id == product_id, models.Product.is_active == True).first()

def create_product(db: Session, product: schemas.ProductCreate):
    db_product = models.Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def get_cart(db: Session, user_id: UUID):
    return db.query(models.Cart).filter(models.Cart.user_id == user_id).first()

def add_to_cart(db: Session, user: User, product_id: UUID, quantity: int):
    cart = get_cart(db, user.id)
    if not cart:
        cart = models.Cart(user_id=user.id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    product = get_product(db, product_id)
    if not product or not product.is_active or product.stock < quantity:
        raise HTTPException(status_code=400, detail="Producto no disponible o stock insuficiente")
    cart_product = db.query(models.CartProduct).filter_by(cart_id=cart.id, product_id=product_id).first()
    if cart_product:
        cart_product.quantity += quantity
    else:
        cart_product = models.CartProduct(cart_id=cart.id, product_id=product_id, quantity=quantity)
        db.add(cart_product)
    db.commit()
    db.refresh(cart)
    return cart

def checkout_cart(db: Session, user: User):
    cart = get_cart(db, user.id)
    if not cart or not cart.cart_products:
        raise HTTPException(status_code=400, detail="El carrito está vacío")
    total = 0
    order_products = []
    for cp in cart.cart_products:
        product = get_product(db, cp.product_id)
        if not product or product.stock < cp.quantity:
            raise HTTPException(status_code=400, detail=f"Stock insuficiente para {product.title}")
        total += product.price * cp.quantity
        order_products.append({
            'product': product,
            'quantity': cp.quantity,
            'price': product.price
        })
    order_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    order = models.Order(
        order_number=order_number,
        user_id=user.id,
        full_name=user.full_name,
        phone_number=user.phone_number,
        address=user.address,
        total=total,
        status="sold"
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    for op in order_products:
        db_op = models.OrderProduct(
            order_id=order.id,
            product_id=op['product'].id,
            quantity=op['quantity'],
            price=op['price']
        )
        db.add(db_op)
        op['product'].stock -= op['quantity']
    db.query(models.CartProduct).filter_by(cart_id=cart.id).delete()
    db.commit()
    return order

def get_sales_report(db: Session, user: User):
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="No autorizado")
    # Daily sales (últimos 7 días)
    today = datetime.utcnow().date()
    daily_sales = []
    for i in range(7):
        day = today - timedelta(days=i)
        orders = db.query(models.Order).filter(func.date(models.Order.created_at) == day).all()
        total_sales = sum(order.total for order in orders)
        total_orders = len(orders)
        # Productos vendidos ese día
        product_counter = {}
        for order in orders:
            for op in order.order_products:
                pid = op.product_id
                if pid not in product_counter:
                    product_counter[pid] = {"product_id": pid, "title": op.product.title, "units_sold": 0, "total": 0.0}
                product_counter[pid]["units_sold"] += op.quantity
                product_counter[pid]["total"] += op.price * op.quantity
        products = sorted([schemas.ProductSalesSummary(**v) for v in product_counter.values()], key=lambda x: x.units_sold, reverse=True)
        daily_sales.append(schemas.DailySalesReport(
            date=str(day),
            total_sales=total_sales,
            total_orders=total_orders,
            products=products
        ))
    daily_sales = sorted(daily_sales, key=lambda x: x.date, reverse=True)
    # Weekly sales (últimas 4 semanas)
    weekly_sales = []
    for i in range(4):
        week_start = today - timedelta(days=today.weekday() + i*7)
        week_end = week_start + timedelta(days=6)
        orders = db.query(models.Order).filter(
            func.date(models.Order.created_at) >= week_start,
            func.date(models.Order.created_at) <= week_end
        ).all()
        total_sales = sum(order.total for order in orders)
        total_orders = len(orders)
        product_counter = {}
        for order in orders:
            for op in order.order_products:
                pid = op.product_id
                if pid not in product_counter:
                    product_counter[pid] = {"product_id": pid, "title": op.product.title, "units_sold": 0, "total": 0.0}
                product_counter[pid]["units_sold"] += op.quantity
                product_counter[pid]["total"] += op.price * op.quantity
        products = sorted([schemas.ProductSalesSummary(**v) for v in product_counter.values()], key=lambda x: x.units_sold, reverse=True)
        week_label = f"{week_start.isocalendar()[0]}-W{week_start.isocalendar()[1]}"
        weekly_sales.append(schemas.WeeklySalesReport(
            week=week_label,
            total_sales=total_sales,
            total_orders=total_orders,
            products=products
        ))
    weekly_sales = sorted(weekly_sales, key=lambda x: x.week, reverse=True)
    # Product summary (total)
    all_orders = db.query(models.Order).all()
    product_counter = {}
    for order in all_orders:
        for op in order.order_products:
            pid = op.product_id
            if pid not in product_counter:
                product_counter[pid] = {"product_id": pid, "title": op.product.title, "units_sold": 0, "total": 0.0}
            product_counter[pid]["units_sold"] += op.quantity
            product_counter[pid]["total"] += op.price * op.quantity
    product_summary = sorted([schemas.ProductSalesSummary(**v) for v in product_counter.values()], key=lambda x: x.units_sold, reverse=True)
    return schemas.SalesReportResponse(
        daily_sales=daily_sales,
        weekly_sales=weekly_sales,
        product_summary=product_summary
    ) 