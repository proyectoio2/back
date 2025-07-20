from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from src.store import service, schemas
from src.auth.service import get_current_user
from src.database import get_db

# Imports adicionales para WhatsApp
from pydantic import BaseModel
from twilio.rest import Client
from src.config import get_settings

settings = get_settings()
import os
from datetime import datetime
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar cliente de Twilio
twilio_client = Client(get_settings().TWILIO_ACCOUNT_SID, get_settings().TWILIO_AUTH_TOKEN)

router = APIRouter(prefix="/store", tags=["store"])

# ========== TUS ENDPOINTS EXISTENTES (NO CAMBIAR) ==========
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

# ========== NUEVOS SCHEMAS PARA WHATSAPP ==========
class ProductoPedido(BaseModel):
    nombre: str
    cantidad: int
    precio: float

class ConfirmarCompraRequest(BaseModel):
    pedido: str
    direccion: str
    productos: List[ProductoPedido]
    total: float
    cliente_info: dict = {}

class ConfirmarCompraResponse(BaseModel):
    success: bool
    message: str
    pedido_id: str
    whatsapp_sent: bool

# ========== FUNCIÓN PARA ENVIAR WHATSAPP ==========
def enviar_whatsapp_pedido(pedido_data: ConfirmarCompraRequest):
    try:
        # Construir el mensaje
        productos_texto = ""
        for producto in pedido_data.productos:
            productos_texto += f"• {producto.cantidad}x {producto.nombre} — ${producto.precio:,.0f}\n"
        
        mensaje = f"""🛒 *NUEVO PEDIDO RECIBIDO*

🧾 *Pedido:* {pedido_data.pedido}
📅 *Fecha:* {datetime.now().strftime('%d/%m/%Y %H:%M')}
📍 *Dirección:* {pedido_data.direccion}

📦 *Productos:*
{productos_texto}
💰 *Total a pagar:* ${pedido_data.total:,.0f}

¡Nuevo pedido listo para procesar! 🚀"""

        # Enviar mensaje
        message = twilio_client.messages.create(
            from_=get_settings().TWILIO_WHATSAPP_NUMBER,
            body=mensaje,
            to=get_settings().YOUR_WHATSAPP_NUMBER
        )
        
        logger.info(f"WhatsApp enviado exitosamente. SID: {message.sid}")
        return True, message.sid
        
    except Exception as e:
        logger.error(f"Error enviando WhatsApp: {str(e)}")
        return False, str(e)

# ========== NUEVOS ENDPOINTS PARA WHATSAPP ==========
@router.post("/confirm-purchase", response_model=ConfirmarCompraResponse)
def confirmar_compra(pedido: ConfirmarCompraRequest):
    try:
        logger.info(f"Procesando pedido: {pedido.pedido}")
        
        # Aquí puedes agregar lógica adicional como:
        # - Guardar en base de datos usando tu service existente
        # - Validar stock
        # - Procesar pago
        # - etc.
        
        # Enviar WhatsApp
        whatsapp_enviado, whatsapp_resultado = enviar_whatsapp_pedido(pedido)
        
        if not whatsapp_enviado:
            logger.warning(f"WhatsApp no se pudo enviar: {whatsapp_resultado}")
            # No es error crítico, el pedido sigue procesándose
        
        # Respuesta exitosa
        return ConfirmarCompraResponse(
            success=True,
            message="Pedido confirmado exitosamente",
            pedido_id=pedido.pedido,
            whatsapp_sent=whatsapp_enviado
        )
        
    except Exception as e:
        logger.error(f"Error procesando pedido: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error procesando pedido: {str(e)}"
        )

@router.post("/test-whatsapp")
def test_whatsapp():
    """Endpoint para probar el envío de WhatsApp"""
    try:
        test_pedido = ConfirmarCompraRequest(
            pedido="TEST-001",
            direccion="Dirección de prueba, Cochabamba, Bolivia",
            productos=[
                ProductoPedido(nombre="Producto Test", cantidad=1, precio=100.0),
                ProductoPedido(nombre="Otro Producto", cantidad=2, precio=50.0)
            ],
            total=200.0
        )
        
        enviado, resultado = enviar_whatsapp_pedido(test_pedido)
        
        return {
            "success": enviado,
            "message": "WhatsApp de prueba enviado" if enviado else "Error enviando WhatsApp",
            "result": resultado
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))