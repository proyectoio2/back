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

# REEMPLAZA TU checkout_with_notification CON ESTA VERSION SIMPLIFICADA:

@router.post("/cart/checkout")
def checkout_with_notification(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    VERSION SIMPLIFICADA CON MENSAJE BASICO PARA DEBUGGING
    """
    try:
        logger.info(f"🚀 Iniciando checkout para usuario: {current_user.id}")
        
        # 1. Verificar carrito ANTES del checkout
        cart = service.get_cart(db, current_user.id)
        
        if not cart or not cart.cart_products:
            raise HTTPException(status_code=400, detail="El carrito está vacío")
        
        logger.info(f"✅ Carrito encontrado con {len(cart.cart_products)} productos")
        
        # 2. Construir lista simple de productos
        productos_lista = []
        total_calculado = 0
        
        for item in cart.cart_products:
            producto_texto = f"{item.quantity}x {item.product.title} - ${item.product.price}"
            productos_lista.append(producto_texto)
            total_calculado += item.product.price * item.quantity
        
        logger.info(f"💰 Total calculado: ${total_calculado}")
        
        # 3. Procesar checkout
        logger.info("🛒 Procesando checkout...")
        order = service.checkout_cart(db, current_user)
        logger.info(f"✅ Orden creada: {order.order_number}")
        
        # 4. MENSAJE MUY SIMPLE SIN EMOJIS NI FORMATO ESPECIAL
        mensaje_simple = f"""NUEVO PEDIDO
        
Pedido: {order.order_number}
Cliente: {order.full_name}
Telefono: {order.phone_number}
Direccion: {order.address}
Total: ${order.total}

Productos:
{chr(10).join(productos_lista)}

Pedido procesado exitosamente."""
        
        logger.info("📱 Enviando WhatsApp con mensaje simple...")
        logger.info(f"📝 Mensaje a enviar: {repr(mensaje_simple)}")
        
        # 5. Enviar con manejo de errores detallado
        try:
            whatsapp_enviado, resultado_whatsapp = EnviarMensajeAVendedor(mensaje_simple)
            logger.info(f"✅ Resultado WhatsApp: enviado={whatsapp_enviado}, resultado={resultado_whatsapp}")
        except Exception as whatsapp_error:
            logger.error(f"❌ Error específico en WhatsApp: {str(whatsapp_error)}")
            whatsapp_enviado = False
            resultado_whatsapp = str(whatsapp_error)
        
        # 6. Respuesta
        response_data = {
            "id": str(order.id),
            "order_number": order.order_number,
            "full_name": order.full_name,
            "phone_number": order.phone_number,
            "address": order.address,
            "total": order.total,
            "status": order.status,
            "created_at": order.created_at.isoformat(),
            "user_id": str(order.user_id),
            "success": True,
            "message": "Pedido procesado exitosamente",
            "whatsapp_sent": whatsapp_enviado,
            "whatsapp_message_id": resultado_whatsapp if whatsapp_enviado else None,
            # Datos extra para debugging
            "debug_info": {
                "productos_count": len(productos_lista),
                "total_calculado": total_calculado,
                "mensaje_length": len(mensaje_simple),
                "whatsapp_error": None if whatsapp_enviado else resultado_whatsapp
            }
        }
        
        logger.info(f"🎯 Checkout completado - WhatsApp: {whatsapp_enviado}")
        return response_data
        
    except HTTPException as he:
        logger.error(f"🚫 HTTPException: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"💥 Error general en checkout: {str(e)}")
        logger.error(f"📍 Stack trace: {str(e.__class__.__name__)}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error procesando pedido: {str(e)}")


# ENDPOINT TEMPORAL PARA DEBUGGING (agregar después de tus otros endpoints):

@router.post("/debug-whatsapp-config")
def debug_whatsapp_config(current_user=Depends(get_current_user)):
    """Endpoint para verificar configuración de WhatsApp"""
    return {
        "twilio_account_sid_configured": bool(TWILIO_ACCOUNT_SID),
        "twilio_auth_token_configured": bool(TWILIO_AUTH_TOKEN),
        "twilio_whatsapp_number": TWILIO_WHATSAPP_NUMBER,
        "vendedor_whatsapp_number": VENDEDOR_WHATSAPP_NUMBER,
        "twilio_account_sid_preview": TWILIO_ACCOUNT_SID[:10] + "..." if TWILIO_ACCOUNT_SID else None,
        "numbers_format_ok": {
            "twilio_number_starts_with_whatsapp": TWILIO_WHATSAPP_NUMBER.startswith("whatsapp:") if TWILIO_WHATSAPP_NUMBER else False,
            "vendedor_number_starts_with_whatsapp": VENDEDOR_WHATSAPP_NUMBER.startswith("whatsapp:") if VENDEDOR_WHATSAPP_NUMBER else False
        }
    }

# TAMBIEN MEJORA TU FUNCION EnviarMensajeAVendedor:

def EnviarMensajeAVendedor(mensaje: str) -> tuple[bool, str]:
    """
    Función mejorada con más logging para debugging
    """
    try:
        logger.info(f"📱 INICIANDO ENVIO WHATSAPP")
        logger.info(f"📞 Número destino: {VENDEDOR_WHATSAPP_NUMBER}")
        logger.info(f"📱 Número origen: {TWILIO_WHATSAPP_NUMBER}")
        logger.info(f"📝 Longitud mensaje: {len(mensaje)} caracteres")
        logger.info(f"🔧 Account SID: {TWILIO_ACCOUNT_SID[:10]}...")
        
        # Validar configuración
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            raise Exception("Credenciales de Twilio no configuradas")
        
        if not VENDEDOR_WHATSAPP_NUMBER or not TWILIO_WHATSAPP_NUMBER:
            raise Exception("Números de WhatsApp no configurados")
        
        # Enviar mensaje
        logger.info("🚀 Enviando mensaje via Twilio...")
        message = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            body=mensaje,
            to=VENDEDOR_WHATSAPP_NUMBER
        )
        
        logger.info(f"✅ WHATSAPP ENVIADO EXITOSAMENTE")
        logger.info(f"📋 SID: {message.sid}")
        logger.info(f"📊 Status: {message.status}")
        logger.info(f"💰 Price: {message.price}")
        logger.info(f"📅 Date created: {message.date_created}")
        
        return True, message.sid
        
    except Exception as e:
        logger.error(f"❌ ERROR ENVIANDO WHATSAPP:")
        logger.error(f"🔥 Tipo de error: {type(e).__name__}")
        logger.error(f"💬 Mensaje de error: {str(e)}")
        logger.error(f"📱 Número destino usado: {VENDEDOR_WHATSAPP_NUMBER}")
        logger.error(f"📱 Número origen usado: {TWILIO_WHATSAPP_NUMBER}")
        
        return False, str(e)
    

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
            "message": "WhatsApp de prueba enviado exitosamente1010101010" if enviado else "Error enviando WhatsApp de prueba",
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
