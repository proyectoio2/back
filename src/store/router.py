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

from src.config import get_settings
settings = get_settings()


# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de Twilio
TWILIO_ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
TWILIO_WHATSAPP_NUMBER = settings.TWILIO_WHATSAPP_NUMBER
VENDEDOR_WHATSAPP_NUMBER = settings.VENDEDOR_WHATSAPP_NUMBER

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

@router.put("/cart/update", response_model=schemas.Cart)
def update_cart_item(request: schemas.UpdateCartItemRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return service.update_cart_item(db, current_user, request.product_id, request.quantity)

@router.delete("/cart/remove", response_model=schemas.Cart)
def remove_from_cart(request: schemas.RemoveFromCartRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return service.remove_from_cart(db, current_user, request.product_id)

@router.delete("/cart/clear", response_model=schemas.Cart)
def clear_cart(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return service.clear_cart(db, current_user)

@router.post("/cart/checkout", response_model=schemas.Order)
def checkout(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return service.checkout_cart(db, current_user)

@router.get("/reports/sales", response_model=schemas.SalesReportResponse)
def sales_report(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    report = service.get_sales_report(db, current_user)
    return report

# ========== 🔥 FUNCIÓN SIMPLE PARA ENVIAR WHATSAPP (COMO PEDISTE) ==========
def EnviarMensajeAVendedor(mensaje: str) -> tuple[bool, str]:
    """
    Función simple que envía cualquier mensaje al WhatsApp del vendedor
    Parámetros:
        mensaje (str): El texto que queremos enviar
    Retorna:
        tuple: (éxito: bool, resultado: str)
    """
    try:
        logger.info(f"📱 Enviando mensaje a {VENDEDOR_WHATSAPP_NUMBER}")
        logger.info(f"📝 Mensaje: {mensaje[:100]}...")  # Log primeros 100 caracteres
        
        # Enviar mensaje usando Twilio
        message = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            body=mensaje,
            to=VENDEDOR_WHATSAPP_NUMBER
        )
        
        logger.info(f"✅ Mensaje enviado exitosamente. SID: {message.sid}")
        return True, message.sid
        
    except Exception as e:
        logger.error(f"❌ Error enviando mensaje WhatsApp: {str(e)}")
        logger.error(f"🔍 Detalles del error: {repr(e)}")
        return False, str(e)

# ========== 🔥 CHECKOUT PRINCIPAL SIMPLIFICADO ==========
@router.post("/cart/checkout")
def checkout_with_notification(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Procesa el checkout y notifica al vendedor por WhatsApp
    Respuesta simplificada que coincide con lo que espera el frontend
    """
    try:
        logger.info(f"🚀 Iniciando checkout para usuario: {current_user.id}")
        
        # 1. Procesar el checkout
        logger.info("📦 Procesando checkout...")
        order = service.checkout_cart(db, current_user)
        logger.info(f"✅ Orden creada: {order.order_number}")
        
        # 2. Crear mensaje simple (similar al test)
        productos_texto = ""
        for order_product in order.order_products:
            productos_texto += f"• {order_product.quantity}x {order_product.product.title} — ${order_product.price:,.0f}\n"
        
        mensaje_vendedor = f"""🛒 *NUEVO PEDIDO*

📋 Pedido: {order.order_number}
👤 Cliente: {order.full_name}
📞 Teléfono: {order.phone_number}  
📍 Dirección: {order.address}
📅 Fecha: {order.created_at.strftime('%d/%m/%Y %H:%M')}

📦 *Productos:*
{productos_texto}
💰 *Total: ${order.total:,.0f}*

¡Nuevo pedido listo para procesar! 🚀"""
        
        # 3. Enviar WhatsApp usando la función simple
        logger.info("📱 Enviando notificación WhatsApp...")
        whatsapp_enviado, resultado_whatsapp = EnviarMensajeAVendedor(mensaje_vendedor)
        
        if whatsapp_enviado:
            logger.info(f"✅ WhatsApp enviado exitosamente: {resultado_whatsapp}")
        else:
            logger.error(f"❌ Error enviando WhatsApp: {resultado_whatsapp}")
        
        # 4. 🔥 RESPUESTA DIRECTA (como espera el frontend)
        # El frontend busca order.order_number, order.full_name, etc.
        # Así que devolvemos la orden directamente con campos adicionales
        response_data = {
            # Campos de la orden original
            "id": str(order.id),
            "order_number": order.order_number,
            "full_name": order.full_name,
            "phone_number": order.phone_number,
            "address": order.address,
            "total": order.total,
            "status": order.status,
            "created_at": order.created_at.isoformat(),
            "user_id": str(order.user_id),
            "order_products": [
                {
                    "id": str(op.id),
                    "quantity": op.quantity,
                    "price": op.price,
                    "product": {
                        "id": str(op.product.id),
                        "title": op.product.title,
                        "description": op.product.description,
                        "image_url": op.product.image_url
                    }
                }
                for op in order.order_products
            ],
            # Campos adicionales para el frontend
            "success": True,
            "message": "Pedido procesado exitosamente" + (" - Vendedor notificado por WhatsApp" if whatsapp_enviado else " - Error notificando vendedor"),
            "whatsapp_sent": whatsapp_enviado,
            "whatsapp_message_id": resultado_whatsapp if whatsapp_enviado else None
        }
        
        logger.info("🎯 Devolviendo respuesta con estructura híbrida")
        return response_data
        
    except HTTPException as he:
        logger.error(f"❌ HTTPException: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"💥 Error en checkout: {str(e)}")
        logger.error(f"📊 Stack trace:", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Error procesando pedido: {str(e)}"
        )

# ========== 🔥 ENDPOINT TEST MEJORADO ==========
@router.post("/test-whatsapp")
def test_whatsapp():
    """Endpoint para probar WhatsApp usando la función simple"""
    try:
        # Mensaje de prueba simple
        mensaje_test = f"""🧪 *MENSAJE DE PRUEBA*

📅 Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}
📱 Sistema: Funcionando correctamente
🔥 Estado: Test exitoso

Este es un mensaje de prueba del sistema de pedidos. Si recibes esto, ¡WhatsApp está funcionando! 🚀"""
        
        # Usar la función simple
        enviado, resultado = EnviarMensajeAVendedor(mensaje_test)
        
        logger.info(f"Test WhatsApp - Enviado: {enviado}, Resultado: {resultado}")
        
        return {
            "success": enviado,
            "message": "WhatsApp de prueba enviado exitosamente" if enviado else "Error enviando WhatsApp de prueba",
            "result": resultado
        }
        
    except Exception as e:
        logger.error(f"Error en test_whatsapp: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ========== 🔥 MANTÉN TU CHECKOUT ORIGINAL (REEMPLAZA EL TUYO) ==========
# Elimina tu checkout_with_notification actual y usa este:

# ========== STATUS DE WHATSAPP ==========
@router.get("/whatsapp-status")
def whatsapp_status():
    """Verificar configuración de WhatsApp"""
    try:
        config_ok = all([
            TWILIO_ACCOUNT_SID,
            TWILIO_AUTH_TOKEN, 
            TWILIO_WHATSAPP_NUMBER,
            VENDEDOR_WHATSAPP_NUMBER
        ])
        
        return {
            "config_valid": config_ok,
            "twilio_number": TWILIO_WHATSAPP_NUMBER,
            "vendedor_number": VENDEDOR_WHATSAPP_NUMBER,
            "account_sid": TWILIO_ACCOUNT_SID[:10] + "...",  # Solo mostrar primeros caracteres por seguridad
            "message": "Configuración de WhatsApp lista" if config_ok else "Configuración incompleta"
        }
        
    except Exception as e:
        return {
            "config_valid": False,
            "error": str(e)
        }
