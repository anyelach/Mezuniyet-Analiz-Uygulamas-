FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt /app/

RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

COPY . /app/

CMD ["python", "app.py"]
