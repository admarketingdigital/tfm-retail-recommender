import requests
from telegram import InputMediaPhoto
from functools import wraps

from app.responses import chain_descripcion_producto, chain_fuera_de_dominio

# URL por defecto si no hay imagen válida
URL_IMAGEN_DEFAULT = "https://upload.wikimedia.org/wikipedia/commons/1/14/No_Image_Available.jpg"

# 🔸 Verifica si una URL apunta a una imagen válida
def es_imagen_valida(url: str) -> bool:
    """Verifica si la URL responde con un contenido tipo imagen válido."""
    try:
        respuesta = requests.head(url, timeout=3)
        content_type = respuesta.headers.get("Content-Type", "")
        return respuesta.status_code == 200 and "image" in content_type
    except:
        return False

# 🔸 Envía una galería de productos con imagen + descripción a Telegram
async def mostrar_productos_telegram(productos_df, update, context):
    from app.estado import productos_mostrados

    if productos_df.empty:
        await update.message.reply_text("⚠️ No hay productos disponibles para mostrar.")
        return

    productos_df = productos_df.sample(min(5, len(productos_df)))  # hasta 5 productos

    productos_mostrados.clear()
    productos_mostrados.extend(productos_df.reset_index(drop=True).to_dict(orient="records"))

    media_group = []

    for _, row in productos_df.iterrows():
        nombre = row["productdisplayname"]
        imagen = row.get("image_url") or URL_IMAGEN_DEFAULT

        try:
            descripcion = chain_descripcion_producto.invoke({"nombre": nombre}).content.strip()
        except:
            descripcion = "(sin descripción)"

        caption = f"*{nombre}*\n{descripcion}"[:1024]
        media_group.append(InputMediaPhoto(media=imagen, caption=caption, parse_mode="Markdown"))

    try:
        await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group)
    except Exception as e:
        print(f"⚠️ Error al enviar galería: {e}")
        # Fallback con imágenes validadas
        media_group_fallback = []
        for item in media_group:
            imagen_final = item.media if es_imagen_valida(item.media) else URL_IMAGEN_DEFAULT
            media_group_fallback.append(InputMediaPhoto(media=imagen_final, caption=item.caption, parse_mode="Markdown"))

        try:
            await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group_fallback)
        except Exception as e2:
            print(f"❌ Fallo también con imágenes corregidas: {e2}")
            await update.message.reply_text("❌ No se pudo mostrar la galería. Prueba con otra categoría.")


# Función asíncrona para responder a mensajes fuera de dominio directamente en Telegram
async def responder_fuera_de_dominio_telegram(mensaje_usuario, llm, update, context):
    """
    Genera una respuesta amable con el LLM para mensajes fuera del dominio del asistente
    y la envía al usuario por Telegram.
    """
    try:
        respuesta = chain_fuera_de_dominio.invoke({"mensaje_usuario": mensaje_usuario}).content.strip()

    except Exception as e:
        print("⚠️ Error al generar respuesta fuera de dominio:", e)
        respuesta = "Solo puedo ayudarte con productos de moda. ¿Quieres que te recomiende algo?"

    await update.message.reply_text(respuesta)


# 🔸 Decorador que muestra un mensaje temporal "procesando..."
def con_mensaje_temporal(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        msg_temp = None
        try:
            msg_temp = await update.message.reply_text("procesando...")
        except:
            pass

        try:
            resultado = await func(update, context, *args, **kwargs)
        finally:
            if msg_temp:
                try:
                    await context.bot.delete_message(chat_id=msg_temp.chat_id, message_id=msg_temp.message_id)
                except:
                    pass
        return resultado
    return wrapper
