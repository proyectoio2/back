import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, Boolean, Table
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy import func

from src.database import Base

class Product(Base):
    __tablename__ = "products"
    id = Column(PGUUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    image_url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    cart_products = relationship("CartProduct", back_populates="product")
    order_products = relationship("OrderProduct", back_populates="product")

class Cart(Base):
    __tablename__ = "carts"
    id = Column(PGUUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    user = relationship("User")
    cart_products = relationship("CartProduct", back_populates="cart", cascade="all, delete-orphan")

class CartProduct(Base):
    __tablename__ = "cart_products"
    id = Column(PGUUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    cart_id = Column(PGUUID(as_uuid=True), ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    cart = relationship("Cart", back_populates="cart_products")
    product = relationship("Product", back_populates="cart_products")

class Order(Base):
    __tablename__ = "orders"
    id = Column(PGUUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    order_number = Column(String, unique=True, nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    full_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    address = Column(String, nullable=False)
    total = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(String, default="sold", nullable=False)
    user = relationship("User")
    order_products = relationship("OrderProduct", back_populates="order", cascade="all, delete-orphan")

class OrderProduct(Base):
    __tablename__ = "order_products"
    id = Column(PGUUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    order_id = Column(PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    order = relationship("Order", back_populates="order_products")
    product = relationship("Product", back_populates="order_products") 