import os
import re
from flask import Flask, render_template, request
import pdfplumber
from werkzeug.utils import secure_filename

app = Flask(__name__)

# PDF dosyasının yükleneceği klasör
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Geçerli dosya türleri
ALLOWED_EXTENSIONS = {'pdf'}

# cid hatalarını düzeltmek için eşleme
cid_map = {
    "248": "İ",  # büyük İ
    "213": "ı",  # küçük ı
}

def cid_temizle(metin):
    if not isinstance(metin, str):
        return metin

    def degistir(match):
        cid_no = match.group(1)
        return cid_map.get(cid_no, '')

    temiz_metin = re.sub(r'\(cid:(\d+)\)', degistir, metin)
    return temiz_metin

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_ders_bilgileri(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        dersler = []

        pattern = r"(AIB\d{3}|BM\d{3}|FIZ\d{3}|ING\d{3}|MAT\d{3}|TDB\d{3}|KRP\d{3}|MS\d{3}|US\d{3}|SE\d{3})\s+(.+?)\s+(\d+\.\d{1,2})\s+(\d+\.\d{1,2})\s+(YT|YZ|[A-F]{2})"

        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines = text.split("\n")
                for line in lines:
                    matches = re.findall(pattern, line)
                    for match in matches:
                        ders_kodu, ders_ismi, kredi, akts, harf_notu = match
                        ders_ismi = cid_temizle(ders_ismi)
                        dersler.append((ders_kodu, ders_ismi, kredi, akts, harf_notu))

    return dersler

def mezuniyet_hesapla(dersler):
    hatalar = []

    toplam_akts = sum(float(ders[3]) for ders in dersler)
    if toplam_akts < 240:
        hatalar.append(f"Toplam AKTS {toplam_akts}, mezuniyet için en az 240 AKTS gereklidir.")

    ders_kodlari = [ders[0] for ders in dersler]
    if len(ders_kodlari) != len(set(ders_kodlari)):
        hatalar.append("Aynı ders birden fazla kez alınmış. Fazla alınan dersler kontrol edilmeli.")

    us_dersler = [d for d in dersler if d[0].startswith("US")]
    ms_dersler = [d for d in dersler if d[0].startswith("MS")]
    if len(us_dersler) < 1:
        hatalar.append("En az 1 üniversite seçmeli (US kodlu) ders alınmalıdır.")
    if len(ms_dersler) < 1:
        hatalar.append("En az 1 fakülte seçmeli (MS kodlu) ders alınmalıdır.")

    secmeli_ders_kodlari = [
        "BM480", "BM455", "BM437", "BM471", "BM490", "BM495", "BM477", "BM493",
        "BM494", "BM442", "BM430", "BM469", "BM424", "BM451", "BM465", "BM436",
        "BM479", "BM443", "BM445", "BM470"
    ]
    secmeli_dersler = [d for d in dersler if d[0] in secmeli_ders_kodlari]

    if len(secmeli_dersler) < 10:
        hatalar.append(f"Toplamda en az 10 seçmeli (BM kodlu) ders alınmalı. Şu an {len(secmeli_dersler)} tane var.")

    # Yaz stajı kontrolü
    yaz_staji_dersleri = [d for d in dersler if d[0] in ("BM399", "BM499")]

    if not yaz_staji_dersleri:
        hatalar.append("Yaz stajı (BM399 veya BM499) tamamlanmamış.")
    else:
        yaz_staji_yetersiz = any(d[4] == "YZ" for d in yaz_staji_dersleri)
        if yaz_staji_yetersiz:
            hatalar.append("Yaz stajı notu yetersiz (YZ).")

    # Başarısız ders kontrolü (FF, FD, YZ)
    basarisiz_notlar = {"FF", "FD", "YZ"}
    basarisiz_dersler = [d for d in dersler if d[4] in basarisiz_notlar]

    if basarisiz_dersler:
        kodlar = ", ".join(set(d[0] for d in basarisiz_dersler))
        hatalar.append(f"Geçilemeyen ders(ler) var: {kodlar}")

    if not hatalar:
        return "Mezuniyet Şartları Sağlanıyor ✅"
    else:
        return "❌ Mezuniyet için eksikler:\n- " + "\n- ".join(hatalar)




@app.route("/")
def index():
    return render_template("index.html", dersler=None, mezuniyet_durumu=None)

@app.route("/upload", methods=["POST"])
def upload_pdf():
    if 'pdf' not in request.files:
        return "Dosya seçilmedi.", 400

    pdf_file = request.files['pdf']

    if pdf_file and allowed_file(pdf_file.filename):
        filename = secure_filename(pdf_file.filename)
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        pdf_file.save(pdf_path)

        dersler = extract_ders_bilgileri(pdf_path)

        if dersler:
            mezuniyet_durumu = mezuniyet_hesapla(dersler)
            return render_template("index.html", dersler=dersler, mezuniyet_durumu=mezuniyet_durumu)
        else:
            return "Ders bilgileri bulunamadı.", 400

    return "Geçersiz dosya türü.", 400

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)

