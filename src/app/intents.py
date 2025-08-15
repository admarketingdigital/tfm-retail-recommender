import json
from telegram import Update
from telegram.ext import ContextTypes
#import app.estado
from app.estado import get_estado, reset_estado
from app.db import engine
from app.recomendador import (
    obtener_producto_base,
    obtener_recomendaciones_similares,
    df_annoy,
    annoy_index,
    reverse_id_map,
    recomendar_desde_historial_telegram,
    buscar_con_minimo_productos_telegram,
    mostrar_productos_telegram,
    identificar_producto_seleccionado,
    mostrar_detalles_producto_telegram,
    recomendar_productos_similares_annoy_con_llm
)
from app.responses import (
    llm,
    chain_descripcion_producto,
    chain_recomendacion_historial,
    chain_sugerencias_post,
    chain_detectar_id_cliente,
    chain_fuera_de_dominio,
    chain_interpretacion_general,
    chain_detectar_id_cliente
)

from app.utils import responder_fuera_de_dominio_telegram

import pandas as pd

# ➕ función: detectar si el mensaje es un saludo
async def detectar_y_responder_saludo_llm( mensaje_usuario, update, context):
    """
    Detecta si el mensaje del usuario es un saludo mediante LLM.
    Si lo es, genera una respuesta adecuada y la envía por Telegram.
    Devuelve True si fue un saludo, False en caso contrario.
    """
    from langchain_core.prompts import PromptTemplate
    from langchain_core.runnables import RunnableSequence


    chat_id = update.effective_chat.id
    estado = get_estado(chat_id)  
    
    # 1. Prompt para detectar saludo
    prompt_detectar_saludo = PromptTemplate.from_template("""
Analiza el siguiente mensaje y responde solo con "SALUDO" si el usuario está saludando (ej. hola, buenos días, hey, etc.).

En cualquier otro caso responde exactamente con "NO".

Mensaje: "{mensaje_usuario}"
""")

    try:
        es_saludo = RunnableSequence(prompt_detectar_saludo | llm).invoke({"mensaje_usuario": mensaje_usuario}).content.strip().upper()
    except Exception as e:
        print("⚠️ Error detectando saludo:", e)
        return False

    if es_saludo != "SALUDO":
        return False

    # 2. Generar respuesta personalizada con LLM
    prompt_respuesta_saludo = PromptTemplate.from_template("""
Eres un asistente de moda profesional y amable. El usuario te ha saludado.

Cliente identificado: {cliente_identificado}
Nombre del cliente: {nombre}

Redacta un saludo apropiado. Si el cliente no está identificado, sugiere que puede hacerlo para recibir recomendaciones personalizadas.

Si ya está identificado, salúdalo por su nombre y sugiérele explorar productos o ver algo similar.

Máximo 3 frases.
""")

    entrada = {
        "cliente_identificado": "sí" if estado.get("customer_id") else "no",
        "nombre": estado.get("nombre") or "usuario"
    }

    try:
        respuesta = RunnableSequence(prompt_respuesta_saludo | llm).invoke(entrada).content.strip()
    except Exception as e:
        print("⚠️ Error generando saludo:", e)
        respuesta = "👋 ¡Hola! ¿Te gustaría ver alguna prenda o identificarte como cliente?"

    await update.message.reply_text(respuesta)
    return True

# ➕ función: detectar intención general (simplificada)
def detectar_intencion_simple(mensaje_usuario):
    mensaje = mensaje_usuario.lower()

    if any(palabra in mensaje for palabra in ["cliente", "soy", "id"]):
        return "identificar"
    if any(palabra in mensaje for palabra in ["ver", "mostrar", "buscar", "enséñame"]):
        return "buscar"
    if "similares" in mensaje:
        return "similares"
    if any(palabra in mensaje for palabra in ["más info", "detalles", "quiero saber"]):
        return "detalle"
    if "reiniciar" in mensaje:
        return "reiniciar"
    return "nada"

# ➕ función: procesar mensaje completo
def detectar_id_cliente_llm(mensaje):
    try:
        return chain_detectar_id_cliente.invoke({"mensaje": mensaje}).content.strip()
    except Exception as e:
        print("⚠️ Error procesando mensaje con LLM:", e)
        return ""

# ➕ función: obtener nombre cliente
def obtener_nombre_cliente(cid):
    try:
        df = pd.read_sql_query(f"SELECT first_name, last_name FROM customers WHERE customer_id = {cid}", engine)
        if not df.empty:
            return f"{df.iloc[0]['first_name']} {df.iloc[0]['last_name']}"
        return None
    except Exception as e:
        print("❌ Error al buscar cliente:", e)
        return None
        
# ➕ función: generar mensaje de bienvenida
async def generar_mensaje_bienvenida_llm(nombre_cliente):
    """
    Genera un mensaje de bienvenida personalizado usando el LLM para un cliente identificado.
    """
    prompt_saludo = f"""
Eres un asistente de moda amable y profesional. Un cliente se acaba de identificar con el nombre: "{nombre_cliente}".

Redacta un mensaje breve (1 o 2 frases) que le dé la bienvenida al sistema de recomendaciones,
explicando que estás listo para ayudarle a descubrir nuevos artículos de moda que podrían interesarle.
Usa un tono cercano y profesional.
"""
    try:
        respuesta = llm.invoke(prompt_saludo).content.strip()
        return f"🤖 {respuesta}"
    except Exception as e:
        print("⚠️ Error generando mensaje de bienvenida LLM:", e)
        return f"👤 Cliente identificado: {nombre_cliente}. ¡Bienvenido!"

        
# ➕ función: procesar mensaje completo
async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #global estado.estado_usuario, estado.producto_base, estado.productos_mostrados, estado.filtros_actuales
    chat_id = update.effective_chat.id
    estado = get_estado(chat_id)    
    mensaje_usuario = update.message.text.strip()
    
    # 1. Detectar saludo
    if await detectar_y_responder_saludo_llm(mensaje_usuario, update, context):
        return

    # Construcción de entrada para el prompt maestro
    nombre_cliente = estado["nombre"] or "no identificado"
    productos_nombres = [p["productdisplayname"] for p in estado["productos_mostrados"]]
    nombre_producto_base = estado["producto_base"]["productdisplayname"] if estado["producto_base"] else ""

    entrada_llm = {
        "mensaje_usuario": mensaje_usuario,
        "cliente_nombre": nombre_cliente,
        "productos_listados": "\n".join(f"{i+1}. {n}" for i, n in enumerate(productos_nombres)),
    }

    try:
        respuesta_raw = chain_interpretacion_general.invoke(entrada_llm).content.strip()
        decision = json.loads(respuesta_raw)
    except Exception as e:
        print("⚠️ Error interpretando intención:", e)
        await update.message.reply_text("❌ No entendí lo que querías. ¿Podrías reformularlo?")
        return

    accion = decision.get("accion")
    detalles = decision.get("detalles", {})

    # --- Acciones ---
    if accion == "identificar":
        msg_temp = await update.message.reply_text("procesando...")
        texto = detalles.get("texto", mensaje_usuario)
        respuesta_id = detectar_id_cliente_llm(texto)
        if respuesta_id.startswith("ID:"):
            cid = int(respuesta_id.replace("ID:", "").strip())
            nombre = obtener_nombre_cliente(cid)
            if nombre:
                estado["customer_id"] = cid
                estado["nombre"] = nombre             
                mensaje_bienvenida = await generar_mensaje_bienvenida_llm(nombre)
                await update.message.reply_text(mensaje_bienvenida)
                await recomendar_desde_historial_telegram(update, context)
            else:
                await update.message.reply_text(f"⚠️ No encontré ningún cliente con el ID {cid}. Intenta de nuevo.")
        else:
            await update.message.reply_text(respuesta_id)
        await context.bot.delete_message(chat_id=msg_temp.chat_id, message_id=msg_temp.message_id)
        
    elif accion == "buscar":
        msg_temp = await update.message.reply_text("procesando...")
        filtros_detectados = detalles.get("filtros", {})
        productos, filtros_usados = await buscar_con_minimo_productos_telegram(update, context, filtros_detectados)
        estado["filtros_actuales"] = filtros_usados
        if productos.empty:
            await update.message.reply_text("❌ No encontré productos con esos filtros. ¿Quieres probar otra categoría o color?")
        else:
            #productos_mostrados = productos.reset_index(drop=True).to_dict(orient="records")
            #for p in productos_mostrados:
            #    if "product_id" not in p and "id" in p:
            #        p["product_id"] = p["id"]
            await mostrar_productos_telegram(productos, update, context)
            print("despues de mostrar productos",estado["productos_mostrados"])
            await update.message.reply_text("¿Quieres ver más información o productos similares de alguno?")
        await context.bot.delete_message(chat_id=msg_temp.chat_id, message_id=msg_temp.message_id)
    elif accion == "detalle":
        msg_temp = await update.message.reply_text("procesando...")
        producto = identificar_producto_seleccionado(update, mensaje_usuario, estado["productos_mostrados"])
        if producto:
            await mostrar_detalles_producto_telegram(producto, update, context)
        else:
            await update.message.reply_text("❌ No entendí a qué producto te refieres. Puedes decir su número o parte del nombre.")
        await context.bot.delete_message(chat_id=msg_temp.chat_id, message_id=msg_temp.message_id)
    elif accion == "similares":
        #print("mensaje usuario: ", mensaje_usuario)
        #print("procutos mostrados: ", productos_mostrados)
        msg_temp = await update.message.reply_text("procesando...")
        producto = identificar_producto_seleccionado(update, mensaje_usuario, estado["productos_mostrados"])
        if producto:
            estado["producto_base"] = producto
        elif not estado["producto_base"]:
            await update.message.reply_text("📌 No entendí qué producto quieres comparar. Selecciona uno primero.")
            return

        await update.message.reply_text(f"🔁 Buscando productos similares a: {estado['producto_base']['productdisplayname']}")
        await recomendar_productos_similares_annoy_con_llm(
            estado["producto_base"],
            df_annoy,
            annoy_index,
            reverse_id_map,
            llm,
            update,
            context
        )
        await context.bot.delete_message(chat_id=msg_temp.chat_id, message_id=msg_temp.message_id)
    elif accion == "reiniciar":
        reset_estado(chat_id)
        await update.message.reply_text("🔄 He reiniciado tu sesión. Puedes empezar una nueva búsqueda o identificarte.")

    elif accion == "nada":
        await responder_fuera_de_dominio_telegram(mensaje_usuario, llm, update, context)
        return
