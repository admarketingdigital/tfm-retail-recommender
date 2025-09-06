import os, json, boto3
from annoy import AnnoyIndex

INDEX_PATH = "data/products.ann"
META_PATH = "data/products_meta.json"
INFO_PATH = "data/index_info.json"

INDEX = None
INDEX_DIM = None
PRODUCT_METADATA = {}
PRODUCT_ID_MAP = {}
REVERSE_ID_MAP = {}

def _download_from_s3(bucket: str, key: str, dest: str):
    s3 = boto3.client("s3")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    s3.download_file(bucket, key, dest)
    print(f"☁️ Descargado {key} desde S3 → {dest}")

def load_index():
    """
    Carga el índice Annoy y metadatos. 
    - Si los ficheros existen en local: se cargan directamente.
    - Si no existen y hay bucket configurado: se descargan de S3.
    """
    global INDEX, INDEX_DIM, PRODUCT_METADATA, PRODUCT_ID_MAP, REVERSE_ID_MAP

    if INDEX is None:
        # Comprobar que tenemos los 3 ficheros
        missing = [p for p in (INDEX_PATH, META_PATH, INFO_PATH) if not os.path.exists(p)]

        if missing:
            bucket = os.getenv("ANNOY_BUCKET")
            if not bucket:
                raise RuntimeError(f"Faltan ficheros {missing} y no hay ANNOY_BUCKET configurado")
            
            # Descargar desde S3
            _download_from_s3(bucket, "indices/products.ann", INDEX_PATH)
            _download_from_s3(bucket, "indices/products_meta.json", META_PATH)
            _download_from_s3(bucket, "indices/index_info.json", INFO_PATH)

        # Leer info de dimensiones
        with open(INFO_PATH, "r", encoding="utf-8") as f:
            info = json.load(f)
        INDEX_DIM = info["dim"]

        # Cargar Annoy
        INDEX = AnnoyIndex(INDEX_DIM, "angular")
        INDEX.load(INDEX_PATH)

        # Cargar metadatos
        with open(META_PATH, "r", encoding="utf-8") as f:
            PRODUCT_METADATA = json.load(f)

        # Reconstruir mapas
        PRODUCT_ID_MAP = {i: int(pid) for i, pid in enumerate(PRODUCT_METADATA.keys())}
        REVERSE_ID_MAP = {int(pid): i for i, pid in enumerate(PRODUCT_METADATA.keys())}

        print(f"✅ Índice Annoy cargado ({len(PRODUCT_METADATA)} productos, dim={INDEX_DIM})")

    return INDEX
