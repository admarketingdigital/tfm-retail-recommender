import random
import pandas as pd
import json
from annoy import AnnoyIndex
from sqlalchemy import text
from app.db import engine
#import app.estado
from app.estado import get_estado
from app.config import OPENAI_API_KEY
from langchain_openai import ChatOpenAI
from app.utils import es_imagen_valida
from app.responses import (
    chain_descripcion_producto,
    chain_recomendacion_historial,
    chain_sugerencias_post,
    chain_detectar_id_cliente,
    chain_fuera_de_dominio,
    chain_interpretacion_general,
    chain_detectar_id_cliente,
    chain_ampliacion_filtros,
    chain_validar_filtros_llm,
    chain_seleccion,
    chain_ampliar_info_producto
)

from telegram import InputMediaPhoto


URL_IMAGEN_DEFAULT = "https://upload.wikimedia.org/wikipedia/commons/1/14/No_Image_Available.jpg"

# Inicializar el modelo LLM (GPT-5)
llm = ChatOpenAI(model="gpt-5", temperature=0.5, openai_api_key=OPENAI_API_KEY)

# --- Cargar productos desde la base de datos
query_productos = """
SELECT pf.*, p.productdisplayname, p.image_url
FROM public.product_features_encoded pf
LEFT JOIN (
    SELECT DISTINCT product_id, productdisplayname, image_url
    FROM public.cleaned_base_table
) p ON pf.product_id = p.product_id
"""

try:
    df_annoy = pd.read_sql(query_productos, engine)
    print(f"✅ Datos de productos cargados: {len(df_annoy)} registros")
except Exception as e:
    print("❌ Error al cargar productos:", e)
    df_annoy = pd.DataFrame()

# --- Construir índice Annoy
feature_cols = [col for col in df_annoy.columns if col not in ['product_id', 'productdisplayname', 'image_url']]
vector_dim = len(feature_cols)
annoy_index = AnnoyIndex(vector_dim, 'angular')

product_id_map = {}
reverse_id_map = {}

for i, row in df_annoy.iterrows():
    try:
        vector = row[feature_cols].values.astype('float32')
        annoy_index.add_item(i, vector)
        product_id_map[i] = row['product_id']
        reverse_id_map[int(row['product_id'])] = i
    except Exception as e:
        print(f"⚠️ Error con producto {row.get('product_id', 'N/A')}: {e}")

annoy_index.build(10)
print(f"✅ Índice Annoy construido con {annoy_index.get_n_items()} productos")


def construir_where_clause(filtros):
    condiciones = []
    for col, val in filtros.items():
        if isinstance(val, list):
            valores_sql = ", ".join(f"'{v}'" for v in val)
            condiciones.append(f"{col} IN ({valores_sql})")
        else:
            condiciones.append(f"{col} = '{val}'")
    return " AND ".join(condiciones) if condiciones else "TRUE"

def buscar_productos_en_db(filtros, limit=10):
    where_clause = construir_where_clause(filtros)
    query = f"""
    SELECT id, productdisplayname, image_url
    FROM products
    WHERE {where_clause}
    LIMIT {limit}
    """
    try:
        return pd.read_sql_query(query, engine)
    except Exception as e:
        print("❌ Error al buscar productos:", e)
        return pd.DataFrame()


# --- Función pública para recomendar productos similares
def obtener_recomendaciones_similares(producto_id_base, n=5):
    if producto_id_base not in reverse_id_map:
        return []

    idx_base = reverse_id_map[producto_id_base]
    vecinos_ids, distancias = annoy_index.get_nns_by_item(idx_base, n + 1, include_distances=True)
    vecinos = [
        (product_id_map[i], round(1 - dist, 3))
        for i, dist in zip(vecinos_ids, distancias)
        if product_id_map[i] != producto_id_base
    ]
    return vecinos[:n]

# Función para obtener producto base como diccionario
def obtener_producto_base(producto_id):
    try:
        producto = df_annoy[df_annoy['product_id'] == producto_id].iloc[0]
        return producto.to_dict()
    except Exception as e:
        print("❌ Error obteniendo producto base:", e)
        return None

def obtener_producto_historial(cliente_id):
    """
    Devuelve un product_id aleatorio del historial de compras o visualizaciones del cliente.
    """
    try:
        query = f"""
        SELECT pem.product_id, p.productdisplayname, p.image_url 
        FROM customers c
        JOIN transactions t ON c.customer_id = t.customer_id
        JOIN click_stream cs ON t.session_id = cs.session_id
        JOIN product_event_metadata pem ON cs.event_id = pem.event_id
        JOIN products p ON pem.product_id = p.id
        WHERE c.customer_id = {cliente_id}
        """
        df = pd.read_sql_query(query, engine)
        if df.empty:
            return None
        return int(df.sample(1)['product_id'].values[0])
    except Exception as e:
        print("❌ Error al obtener historial del cliente:", e)
        return None

async def recomendar_desde_historial_telegram(update, context):
#    global estado.producto_base, estado.productos_mostrados, estado.estado_usuario
    chat_id = update.effective_chat.id
    estado = get_estado(chat_id)    
    
    cliente_id = estado.get("customer_id")
    nombre_cliente = estado.get("nombre")

    if not cliente_id:
        await update.message.reply_text("❌ Aún no estás identificado como cliente.")
        return

    # 1. Obtener producto base del historial
    msg_temp = await update.message.reply_text("procesando...")
    producto_id_base = obtener_producto_historial(cliente_id)
    if not producto_id_base:
        await update.message.reply_text("ℹ️ No encontramos historial previo. Puedes pedirme algún tipo de prenda o color.")
        await context.bot.delete_message(chat_id=msg_temp.chat_id, message_id=msg_temp.message_id)
        return

    if producto_id_base not in reverse_id_map:
        await update.message.reply_text("⚠️ No pude encontrar ese producto en el sistema. Intenta otra búsqueda.")
        await context.bot.delete_message(chat_id=msg_temp.chat_id, message_id=msg_temp.message_id)
        return

    await context.bot.delete_message(chat_id=msg_temp.chat_id, message_id=msg_temp.message_id)
    
    # 2. Obtener producto base y su información
    
    estado["producto_base"] = df_annoy[df_annoy['product_id'] == producto_id_base].iloc[0].to_dict()
    nombre_base = estado["producto_base"]["productdisplayname"]
    imagen_base = estado["producto_base"].get("image_url") or "https://upload.wikimedia.org/wikipedia/commons/1/14/No_Image_Available.jpg"
    imagen_fallback = "https://upload.wikimedia.org/wikipedia/commons/1/14/No_Image_Available.jpg"

    # 3. Mostrar saludo inicial
    
    await update.message.reply_text("Como has comprado o visualizado...")

    # 4. Mostrar imagen y descripción del producto base
    msg_temp = await update.message.reply_text("cargando producto...") 

    prompt_desc_base = f"""
Eres un asistente de moda. Un cliente ha mostrado interés en el producto: "{nombre_base}".
Describe brevemente en 1 o 2 frases por qué este producto podría ser atractivo.
"""
    try:
        comentario_base = llm.invoke(prompt_desc_base).content.strip()
    except:
        comentario_base = "(sin descripción)"

    caption_base = f"*{nombre_base}*\n_{comentario_base}_"
    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=imagen_base,
            caption=caption_base,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"⚠️ Error con imagen base. Usando fallback: {e}")
        try:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=imagen_fallback,
                caption=caption_base,
                parse_mode="Markdown"
            )
        except Exception as e2:
            print(f"❌ Error con imagen fallback: {e2}")
            await update.message.reply_text(f"🧾 {caption_base}")
    
    await context.bot.delete_message(chat_id=msg_temp.chat_id, message_id=msg_temp.message_id)
    
    # 5. Generar mensaje personalizado desde LLM
    msg_temp = await update.message.reply_text("procesando...")
    entrada_llm = {
        "nombre_cliente": nombre_cliente,
        "nombre_producto_base": nombre_base
    }
    try:
        mensaje_bienvenida = chain_recomendacion_historial.invoke(entrada_llm).content.strip()
        await update.message.reply_text(f"🤖 {mensaje_bienvenida}")
    except Exception as e:
        print("⚠️ Error generando mensaje LLM:", e)
        
    await context.bot.delete_message(chat_id=msg_temp.chat_id, message_id=msg_temp.message_id)
    
    # 6. Buscar productos similares con Annoy
    msg_temp = await update.message.reply_text("buscando productos similares, espere un momento...")
    
    idx_base = reverse_id_map[producto_id_base]
    vecinos_ids, distancias = annoy_index.get_nns_by_item(idx_base, 11, include_distances=True)
    vecinos_filtrados = [(i, d) for i, d in zip(vecinos_ids, distancias) if product_id_map[i] != producto_id_base]
    seleccion = random.sample(vecinos_filtrados, min(5, len(vecinos_filtrados)))

    # 7. Preparar galería de recomendaciones
    media_group = []
    estado["productos_mostrados"] = []

    for idx, dist in seleccion:
        prod = df_annoy.iloc[idx]
        nombre = prod["productdisplayname"]
        imagen = prod.get("image_url") or imagen_fallback
        sim = round(1 - dist, 3)

        prompt_desc = f"""
Eres un asistente de moda. El cliente mostró interés en el producto: "{nombre_base}".
Vas a recomendar el producto "{nombre}". Genera una frase corta (máx. 15 palabras) explicando por qué le podría gustar.
"""
        try:
            comentario = llm.invoke(prompt_desc).content.strip()
        except:
            comentario = "(sin comentario)"

        caption = f"*{nombre}*\n_{comentario}_\n*Similitud: {sim}*"
        media_group.append(InputMediaPhoto(media=imagen, caption=caption, parse_mode="Markdown"))

        estado["productos_mostrados"].append({
            "product_id": int(prod["product_id"]),
            "productdisplayname": nombre,
            "image_url": imagen
        })

    # 8. Enviar galería

    try:
        await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group)
    except Exception as e:
        print(f"⚠️ Error al enviar galería: {e}")
        print("🔄 Reintentando con imágenes validadas...")

        # Validar imágenes una a una y reemplazar las que no sirvan
        media_group_fallback = []
        for item in media_group:
            imagen_final = item.media if es_imagen_valida(item.media) else URL_IMAGEN_DEFAULT
            media_group_fallback.append(InputMediaPhoto(media=imagen_final, caption=item.caption))

        try:
            await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group_fallback)
        except Exception as e2:
            print(f"❌ Fallo también con imágenes corregidas: {e2}")
            await update.message.reply_text("❌ No se pudo mostrar la galería. Inténtalo más tarde.")

    
#    try:
#        await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group)
#    except Exception as e:
#        print("❌ Error enviando galería:", e)
#        await update.message.reply_text("⚠️ No pude mostrar las recomendaciones. Intenta más tarde.")

        
    await context.bot.delete_message(chat_id=msg_temp.chat_id, message_id=msg_temp.message_id)
    
    # 9. Sugerencia post-recomendación
    msg_temp = await update.message.reply_text("procesando...") 
    try:
        mensaje_post = chain_sugerencias_post.invoke({}).content.strip()
        await update.message.reply_text(f"🤖 {mensaje_post}")
    except:
        await update.message.reply_text("¿Quieres ver el detalle de alguno o ver más similares a alguno mostrado?")
    
    await context.bot.delete_message(chat_id=msg_temp.chat_id, message_id=msg_temp.message_id)


def obtener_contexto_columnas():
    """
    Devuelve un string con los valores posibles por columna de productos,
    que será usado como contexto para el LLM al validar filtros.
    """
    columnas = [
        "gender", "mastercategory", "subcategory", 
        "articletype", "basecolour", "season", "year", "usage"
    ]
    contexto = ""
    for col in columnas:
        try:
            valores = pd.read_sql_query(
                f"SELECT DISTINCT {col} FROM products WHERE {col} IS NOT NULL LIMIT 100", 
                engine
            )[col].dropna().unique()
            contexto += f"{col}: {', '.join(map(str, valores))}\n"
        except Exception:
            contexto += f"{col}: [error al obtener valores]\n"
    return contexto.strip()


def validar_y_corregir_filtros_llm(filtros_propuestos: dict) -> dict:
    """
    Toma un conjunto de filtros (propuestos por el LLM o el usuario) y los valida
    frente a los valores reales disponibles en la base de datos.

    Retorna un diccionario con los filtros corregidos.
    """
    contexto_columnas = obtener_contexto_columnas()

    try:
        entrada = {
            "filtros_propuestos": filtros_propuestos,
            "contexto_columnas": contexto_columnas
        }
        respuesta = chain_validar_filtros_llm.invoke(entrada)
        return json.loads(respuesta.content)["filtros"]
    except Exception as e:
        print("⚠️ Error al validar y corregir filtros con el LLM:", e)
        return filtros_propuestos  # Devuelve tal cual si falla

def solicitar_filtros_alternativos_llm(update, filtros_actuales: dict, productos_actuales: pd.DataFrame) -> dict:
    """
    Solicita al LLM una ampliación razonable de los filtros si los resultados son escasos.
    """
    chat_id = update.effective_chat.id
    estado = get_estado(chat_id)  
    
    contexto_columnas = obtener_contexto_columnas()
    
    try:
        entrada_llm = {
            "filtros_actuales": estado["filtros_actuales"],
            "num_resultados": len(productos_actuales),
            "contexto_columnas": contexto_columnas
        }
        respuesta = chain_ampliacion_filtros.invoke(entrada_llm)
        return json.loads(respuesta.content)
    except Exception as e:
        print("⚠️ No se pudo obtener filtros alternativos del LLM:", e)
        return {}

async def buscar_con_minimo_productos_telegram(update, context, filtros_iniciales, minimo=5, max_intentos=3):
#    global estado.estado_usuario, estado.producto_base, estado.productos_mostrados, estado.filtros_actuales
    """
    Búsqueda inteligente para Telegram:
    - Valida y corrige filtros con el LLM.
    - Si hay pocos resultados, amplía los filtros.
    - Muestra progreso al usuario en Telegram.
    """
    chat_id = update.effective_chat.id
    estado = get_estado(chat_id) 
    
    intentos = 0
    estado["filtros_actuales"] = validar_y_corregir_filtros_llm(filtros_iniciales)
    print("filtros_iniciales: ",filtros_iniciales)
    print("validar_y_corregir_filtros_llm: ",estado["filtros_actuales"])
    while intentos < max_intentos:
        productos = buscar_productos_en_db(estado["filtros_actuales"])

        if len(productos) >= minimo:
            await update.message.reply_text(f"🎯 Encontré productos que pueden interesarte.")
            return productos, estado["filtros_actuales"]

        if(len(productos)==0):
            await update.message.reply_text(
            f"🤏 No encontré productos. Estoy buscando más opciones parecidas..."
            )
        else:
            await update.message.reply_text(
                f"🤏 Solo encontré {len(productos)} producto/s. Estoy buscando más opciones parecidas..."
            )
        intentos += 1

        nuevos_datos = solicitar_filtros_alternativos_llm(update, estado["filtros_actuales"], productos)
        print("solicitar_filtros_alternativos",nuevos_datos)
        if nuevos_datos and "filtros" in nuevos_datos:
            estado["filtros_actuales"] = nuevos_datos["filtros"]
            print(f"🧠 Filtros ampliados: {estado['filtros_actuales']}")
        else:
            await update.message.reply_text("⚠️ No pude ampliar los filtros. Te mostraré lo mejor que encontré.")
            break

    return productos, estado["filtros_actuales"]


async def mostrar_productos_telegram(productos_df, update, context):
#    global estado.productos_mostrados

    chat_id = update.effective_chat.id
    estado = get_estado(chat_id)
    
    try:
        if productos_df.empty:
            await update.message.reply_text("⚠️ No hay productos disponibles para mostrar.")
            return

        
        productos_df = productos_df.sample(min(5, len(productos_df)))  # hasta 5 productos

        estado["productos_mostrados"]=[]
        estado["productos_mostrados"] = productos_df.reset_index(drop=True).to_dict(orient="records")
        print("productos mostrados: ",estado["productos_mostrados"])
        for p in estado["productos_mostrados"]:
            if "product_id" not in p and "id" in p:
                p["product_id"] = p["id"]
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
            print("🔄 Reintentando con imágenes validadas...")

            # Validar imágenes una a una y reemplazar las que no sirvan
            media_group_fallback = []
            for item in media_group:
                imagen_final = item.media if es_imagen_valida(item.media) else URL_IMAGEN_DEFAULT
                media_group_fallback.append(InputMediaPhoto(media=imagen_final, caption=item.caption, parse_mode="Markdown"))

            try:
                await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group_fallback)
            except Exception as e2:
                print(f"❌ Fallo también con imágenes corregidas: {e2}")
                await update.message.reply_text("❌ No se pudo mostrar la galería. Prueba con otra categoría.")
    except Exception as e:
        print(f"❌ Error inesperado al mostrar productos: {e}")
        await update.message.reply_text("❌ Ocurrió un error inesperado al mostrar los productos.")


    except Exception as e:
        print(f"❌ Error al enviar galería: {e}")
        await update.message.reply_text(f"❌ No se pudo mostrar la galería de productos. Error: {e}")

def identificar_producto_seleccionado(update, mensaje_usuario, productos_mostrados):

    chat_id = update.effective_chat.id
    estado = get_estado(chat_id)

    print("identificar_producto, mensaje usuario",mensaje_usuario)
    print("identificar_producto, productos mostrados",estado["productos_mostrados"])
    try:
        productos_numerados = "\n".join([
            f"{i+1}. {p['productdisplayname']}" for i, p in enumerate(estado["productos_mostrados"])
        ])
        entrada = {
            "mensaje_usuario": mensaje_usuario,
            "productos_numerados": productos_numerados
        }

        respuesta = chain_seleccion.invoke(entrada)
        datos = json.loads(respuesta.content.strip())

        idx_raw = datos.get("seleccion", None)
        if idx_raw is None:
            return None

        idx = int(idx_raw)
        if 1 <= idx <= len(estado["productos_mostrados"]):
            return estado["productos_mostrados"][idx - 1]
        else:
            return None
    except Exception as e:
        print("⚠️ Error al identificar el producto:", e)
        return None

async def mostrar_detalles_producto_telegram(producto, update, context):
#    global estado.producto_base

    chat_id = update.effective_chat.id
    estado = get_estado(chat_id)
    
    estado["producto_base"] = producto

    nombre = producto.get("productdisplayname")
    imagen = producto.get("image_url") or "https://upload.wikimedia.org/wikipedia/commons/1/14/No_Image_Available.jpg"

    entrada_llm = {
        "nombre_producto": nombre,
        "cliente_identificado": "sí" if estado.get("customer_id") else "no"
    }

    try:
        descripcion = chain_ampliar_info_producto.invoke(entrada_llm).content.strip()
    except Exception as e:
        descripcion = "(No se pudo generar la descripción.)"
        print("⚠️ Error generando descripción:", e)

    # Enviar imagen ampliada + descripción
    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=imagen,
            caption=f"*{nombre}*\n_{descripcion}_",
            parse_mode="Markdown"
        )
    except Exception as e:
        print("❌ Error al enviar imagen:", e)
        await update.message.reply_text(f"*{nombre}*\n{descripcion}", parse_mode="Markdown")



async def recomendar_productos_similares_annoy_con_llm(producto_base, df_annoy, annoy_index, reverse_id_map, llm, update, context, num_total=10, num_mostrar=5):
#    global estado.productos_mostrados
    try:
           
        # 6. Buscar productos similares con Annoy
        msg_temp = await update.message.reply_text("buscando productos similares, espere un momento...")

        chat_id = update.effective_chat.id
        estado = get_estado(chat_id)
        estado["producto_base"] = producto_base
        producto_id = int(estado["producto_base"]["product_id"])
        nombre_base = estado["producto_base"]["productdisplayname"]
        idx_base = reverse_id_map.get(producto_id)
        
        vecinos_ids, distancias = annoy_index.get_nns_by_item(idx_base, num_total + 1, include_distances=True)
        vecinos_filtrados = [(i, d) for i, d in zip(vecinos_ids, distancias) if product_id_map[i] != producto_id]
        seleccion = random.sample(vecinos_filtrados, min(5, len(vecinos_filtrados)))
    
        # 7. Preparar galería de recomendaciones
        media_group = []
        estado["productos_mostrados"] = []
    
        for idx, dist in seleccion:
            prod = df_annoy.iloc[idx]
            nombre = prod["productdisplayname"]
            imagen = prod.get("image_url") or imagen_fallback
            sim = round(1 - dist, 3)
    
            prompt_desc = f"""
    Eres un asistente de moda. El cliente mostró interés en el producto: "{nombre_base}".
    Vas a recomendar el producto "{nombre}". Genera una frase corta (máx. 15 palabras) explicando por qué le podría gustar.
    """
            try:
                comentario = llm.invoke(prompt_desc).content.strip()
            except:
                comentario = "(sin comentario)"
    
            caption = f"*{nombre}*\n_{comentario}_\n*Similitud: {sim}*"
            media_group.append(InputMediaPhoto(media=imagen, caption=caption, parse_mode="Markdown"))
    
            estado["productos_mostrados"].append({
                "product_id": int(prod["product_id"]),
                "productdisplayname": nombre,
                "image_url": imagen
            })
        #print("productos mostrados similares: ", productos_mostrados)
        # 8. Enviar galería
    
        try:
            await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group)
        except Exception as e:
            print(f"⚠️ Error al enviar galería: {e}")
            print("🔄 Reintentando con imágenes validadas...")
    
            # Validar imágenes una a una y reemplazar las que no sirvan
            media_group_fallback = []
            for item in media_group:
                imagen_final = item.media if es_imagen_valida(item.media) else URL_IMAGEN_DEFAULT
                media_group_fallback.append(InputMediaPhoto(media=imagen_final, caption=item.caption))
    
            try:
                await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group_fallback)
            except Exception as e2:
                print(f"❌ Fallo también con imágenes corregidas: {e2}")
                await update.message.reply_text("❌ No se pudo mostrar la galería. Inténtalo más tarde.")
    
        
    #    try:
    #        await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group)
    #    except Exception as e:
    #        print("❌ Error enviando galería:", e)
    #        await update.message.reply_text("⚠️ No pude mostrar las recomendaciones. Intenta más tarde.")
    
            
        await context.bot.delete_message(chat_id=msg_temp.chat_id, message_id=msg_temp.message_id)

        # 9. Sugerencia post-recomendación
        msg_temp = await update.message.reply_text("procesando...") 
        try:
            mensaje_post = chain_sugerencias_post.invoke({}).content.strip()
            await update.message.reply_text(f"🤖 {mensaje_post}")
        except:
            await update.message.reply_text("¿Quieres ver el detalle de alguno o ver más similares a alguno mostrado?")
        
        await context.bot.delete_message(chat_id=msg_temp.chat_id, message_id=msg_temp.message_id)
        
    except Exception as e:
        print("❌ Error recomendando productos similares:", e)
        await update.message.reply_text("❌ Ocurrió un error mostrando productos similares.")


# Exportar elementos clave para usar en otros módulos
__all__ = ["df_annoy", "annoy_index", "product_id_map", "reverse_id_map", "obtener_recomendaciones_similares", "obtener_producto_base", "recomendar_desde_historial_telegram","buscar_con_minimo_productos_telegram","mostrar_productos_telegram","identificar_producto_seleccionado","mostrar_detalles_producto_telegram","recomendar_productos_similares_annoy_con_llm"]
