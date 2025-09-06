FROM public.ecr.aws/lambda/python:3.12 as builder

RUN microdnf install -y gcc gcc-c++ make

# Instalar dependencias directamente en /var/task
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -t /var/task

# Copiar código y datos al mismo sitio
COPY app /var/task/app
COPY data /var/task/data

CMD ["app.main.handler"]