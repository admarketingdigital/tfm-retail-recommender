from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import ContextTypes

from app.intents import manejar_mensaje
from app.estado import get_estado, reset_estado, limpiar_estados_inactivos
from app.config import TELEGRAM_BOT_TOKEN
from app.utils import con_mensaje_temporal
from app.responses import chain_bienvenida

# --- Handlers de comandos ---

# ⚙️ Se ejecuta automáticamente después de build() y antes de polling
async def configurar_tareas_periodicas(application):
    print("🛠️ Configurando limpieza periódica de sesiones...")
    application.job_queue.run_repeating(
        callback=lambda context: limpiar_estados_inactivos(minutos=60),
        interval=600  # cada 10 minutos
    )

@con_mensaje_temporal
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    reset_estado(chat_id) # reset del estado individual
    
    estado = get_estado(chat_id)
    nombre = estado.get("nombre")
    cliente_identificado = "sí" if nombre else "no"
    nombre_mostrar = nombre or "usuario"

    await update.message.reply_photo(
        photo=open("fondo_bot.png", "rb"),
    )

    entrada = {
        "cliente_identificado": cliente_identificado,
        "nombre": nombre_mostrar
    }

    try:
        mensaje = chain_bienvenida.invoke(entrada).content.strip()
    except Exception as e:
        print("⚠️ Error generando bienvenida con LLM:", e)
        mensaje = "👋 ¡Hola! Soy tu asistente de moda. ¿Te gustaría ver una prenda o identificarte como cliente?"

    await update.message.reply_text(mensaje)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    reset_estado(chat_id)

    # Enviar imagen de bienvenida
    try:
        await update.message.reply_photo(
            photo=open("fondo_bot.png", "rb"),
            caption="🔄 Has reiniciado el asistente.\n\n👋 Bienvenido de nuevo al recomendador de productos.\n\nIdentifícate escribiendo: Cliente 123"
        )
    except Exception as e:
        await update.message.reply_text("🔄 Reinicio exitoso. No se pudo mostrar la imagen de bienvenida.")
        print("[AVISO] No se pudo enviar imagen de portada:", e)
        

async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.estado import estados_usuarios
    await update.message.reply_text(f"📊 Estados activos: {len(estados_usuarios)} usuarios.")

async def handle_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    estado = get_estado(chat_id)
    print(f"📩 LLEGÓ MENSAJE de {chat_id}: {update.message.text}")
    await update.message.reply_text(f"✅ Estado actual:\n{estado}")

# --- Main async ---
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(configurar_tareas_periodicas).build()

    # Comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("estado", estado))
    
    # Mensajes de texto
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))
    
    print("🤖 Bot iniciado. Esperando mensajes...")
    app.run_polling()

# --- Entry point ---
if __name__ == "__main__":
    main()
