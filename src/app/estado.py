from datetime import datetime, timedelta

# Diccionario global de estados por chat_id
estados_usuarios = {}


def get_estado(chat_id):
    if chat_id not in estados_usuarios:
        estados_usuarios[chat_id] = {
            "customer_id": None,
            "nombre": None,
            "producto_base": None,
            "productos_mostrados": [],
            "filtros_actuales": {},
            "timestamp": datetime.now()
        }
    else:
        estados_usuarios[chat_id]["timestamp"] = datetime.now()
    return estados_usuarios[chat_id]

def reset_estado(chat_id):
    estados_usuarios[chat_id] = {
        "customer_id": None,
        "nombre": None,
        "producto_base": None,
        "productos_mostrados": [],
        "filtros_actuales": {},
        "timestamp": datetime.now()
    }

def limpiar_estados_inactivos(minutos=60):
    ahora = datetime.now()
    inactivos = [cid for cid, estado in estados_usuarios.items()
                 if ahora - estado.get("timestamp", ahora) > timedelta(minutes=minutos)]
    for cid in inactivos:
        del estados_usuarios[cid]