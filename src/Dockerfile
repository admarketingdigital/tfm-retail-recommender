# Imagen base oficial de Python
FROM python:3.11-slim

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalar gcc y otras herramientas de compilación necesarias
RUN apt-get update && \
    apt-get install -y build-essential && \
    apt-get clean

# Copiar archivos del proyecto
COPY . .

# Instalar dependencias
RUN pip install --upgrade pip && pip install -r requirements.txt

# Ejecutar el bot
CMD ["python", "main.py"]