# Python 3.9 resmi imajını temel alıyoruz
FROM python:3.9-slim

# Çalışma dizini
WORKDIR /app

# Bağımlılık dosyasını kopyala
COPY requirements.txt .

# Pip güncelle ve bağımlılıkları yükle
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

# Uygulama dosyalarını kopyala
COPY . .

# Flask uygulamasını çalıştır
CMD ["python", "FlaskApp/app.py"]

