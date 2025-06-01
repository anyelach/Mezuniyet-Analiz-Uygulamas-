import os
import re
from flask import Flask, render_template, request
import pdfplumber
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'pdf'}

# Sadece İ ve ı karakteri düzeltmesi
def cid_temizle(metin):
    if not isinstance(metin, str):
        return metin
    metin = metin.replace("(cid:248)", "İ")
    metin = metin.replace("(cid:213)", "ı")
    return metin

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_ders_bilgileri(pdf_path):
    MANUEL_DERSLER = {
        "BM401": ("Bilgisayar Mühendisliği Proje Tasarımı", "2.0", "3.0"),
        "BM496": ("Bilgi Mühendisliği ve Büyük Veriye Giriş", "3.0", "5.0"),
        "BM495": ("İleri Gömülü Sistem Uygulamaları", "3.0", "5.0"),
    }

    dersler = []

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    # Önce manuel dersler
    for kod, (isim, kredi, akts) in MANUEL_DERSLER.items():
        if kod in text:
            not_pattern = rf"{kod}.*?(\d+\.\d+\s+\d+\.\d+\s+(YT|YZ|[A-F]{{2}}))"
            match = re.search(not_pattern, text, re.DOTALL)
            if match:
                notu = match.group(2)
                dersler.append((kod, isim, kredi, akts, notu))
                print(f"✅ MANUEL: {kod} - {isim}")

    # Diğer dersleri yakala
    pattern = r"""
        (?P<kod>\b[A-Z]{2,3}\d{3}\b)\s+
        (?P<isim>(?:(?!\d+\.\d+)[^\n])+?)\s+
        (?P<kredi>\d+\.\d+)\s+
        (?P<akts>\d+\.\d+)\s+
        (?P<notu>YT|YZ|[A-F]{2})
    """

    for match in re.finditer(pattern, text, re.VERBOSE | re.DOTALL):
        kod = match.group("kod")
        if kod not in MANUEL_DERSLER:
            isim_raw = match.group("isim")
            isim_clean = cid_temizle(" ".join(isim_raw.split()))
            dersler.append((kod, isim_clean, match.group("kredi"), match.group("akts"), match.group("notu")))
            print(f"✔ OTOMATİK: {kod} - {isim_clean}")

    return dersler

def mezuniyet_hesapla(dersler):
    hatalar = []
    unique_dersler = {}
    for d in dersler:
        unique_dersler[d[0]] = d

    toplam_akts = sum(float(d[3]) for d in unique_dersler.values())
    if toplam_akts < 240:
        hatalar.append(f"Toplam AKTS {toplam_akts}, mezuniyet için en az 240 AKTS gereklidir.")

    ders_kodlari = [d[0] for d in dersler]
    if len(ders_kodlari) != len(set(ders_kodlari)):
        hatalar.append("Aynı ders birden fazla kez alınmış. Fazla alınan dersler kontrol edilmeli.")

    us_dersler = [d for d in unique_dersler.values() if d[0].startswith("US")]
    ms_dersler = [d for d in unique_dersler.values() if d[0].startswith("MS")]
    if len(us_dersler) < 1:
        hatalar.append("En az 1 üniversite seçmeli (US kodlu) ders alınmalıdır.")
    if len(ms_dersler) < 1:
        hatalar.append("En az 1 fakülte seçmeli (MS kodlu) ders alınmalıdır.")

    secmeli_ders_kodlari = [
        "BM480", "BM455", "BM437", "BM471", "BM490", "BM495", "BM477", "BM493",
        "BM494", "BM442", "BM430", "BM469", "BM424", "BM451", "BM465", "BM436",
        "BM479", "BM443", "BM445", "BM470", "BM473", "BM420", "BM421", "BM422",
        "BM423", "BM425", "BM426", "BM427", "BM428", "BM429", "BM431", "BM432",
        "BM433", "BM434", "BM435", "BM438", "BM439", "BM440", "BM441", "BM444",
        "BM447", "BM449", "BM453", "BM457", "BM459", "BM461", "BM463", "BM467",
        "BM472", "BM474", "BM475", "BM476", "BM478", "BM481", "BM482", "BM483",
        "BM485", "BM486", "BM487", "BM488", "BM489", "BM491", "BM492", "BM496", "MTH401"
    ]
    secmeli_dersler = [d for d in unique_dersler.values() if d[0] in secmeli_ders_kodlari]
    if len(secmeli_dersler) < 10:
        hatalar.append(f"Toplamda en az 10 seçmeli (BM kodlu) ders alınmalı. Şu an {len(secmeli_dersler)} adet var.")

    yaz_staji_dersleri = [d for d in unique_dersler.values() if d[0] in ("BM399", "BM499")]
    if not yaz_staji_dersleri:
        hatalar.append("Yaz stajı (BM399 veya BM499) tamamlanmamış.")
    elif any(d[4] == "YZ" for d in yaz_staji_dersleri):
        hatalar.append("Yaz stajı notu yetersiz (YZ).")

    basarisiz_notlar = {"FF", "FD", "YZ"}
    basarisiz_dersler = [d for d in unique_dersler.values() if d[4] in basarisiz_notlar]
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
