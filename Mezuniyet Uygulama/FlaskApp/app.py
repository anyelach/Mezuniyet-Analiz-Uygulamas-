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
        tum_metin = ""
        for page in pdf.pages:
            tum_metin += page.extract_text() + "\n"
        
        # Debug için PDF'nin ham çıktısını kaydet
        with open("pdf_ham_cikti.txt", "w", encoding="utf-8") as f:
            f.write(tum_metin)
        
        # Önce tüm metni temizle (CID'leri düzelt)
        temiz_metin = cid_temizle(tum_metin)
        
        # Özel durum: BM401 için manuel düzeltme
        temiz_metin = temiz_metin.replace("BM401 2.0 3.0 CB", "BM401 Bilgisayar Mühendisliği Proje Tasarımı 2.0 3.0 CB")
        
        # Ders kodlarını bul
        ders_kodlari = re.finditer(
            r"\b(AIB\d{3}|BM\d{3}|FIZ\d{3}|ING\d{3}|MAT\d{3}|TDB\d{3}|KRP\d{3}|MS\d{3}|US\d{3}|SE\d{3})\b", 
            temiz_metin
        )
        
        dersler = []
        pozisyonlar = [match.start() for match in ders_kodlari]
        
        for i in range(len(pozisyonlar)):
            baslangic = pozisyonlar[i]
            son = pozisyonlar[i+1] if i+1 < len(pozisyonlar) else len(temiz_metin)
            ders_bloku = temiz_metin[baslangic:son]
            
            # Geliştirilmiş regex pattern
            match = re.search(
                r"(?P<kod>\b[A-Z]{2,3}\d{3}\b)\s+"
                r"(?P<isim>(?!\d+\.\d+)[^\n]+?)\s+"
                r"(?P<kredi>\d+\.\d+)\s+"
                r"(?P<akts>\d+\.\d+)\s+"
                r"(?P<notu>YT|YZ|[A-F]{2})\b",
                ders_bloku,
                re.DOTALL
            )
            
            if match:
                ders_ismi = " ".join(match.group("isim").split()).strip()
                dersler.append((
                    match.group("kod"),
                    ders_ismi,
                    match.group("kredi"),
                    match.group("akts"),
                    match.group("notu")
                ))
                print(f"✔️ BAŞARILI: {match.group('kod')} | {ders_ismi}")
            else:
                print(f"❌ EŞLEŞMEYEN: {ders_bloku[:100]}...")
    
    return dersler





def mezuniyet_hesapla(dersler):
    hatalar = []

    # Aynı ders tekrar alındıysa, sadece sonuncusunu al
    unique_dersler = {}
    for d in dersler:
        unique_dersler[d[0]] = d  # en son alınanı tutar

    # Başarılı/başarısız fark etmeksizin tüm AKTS'leri topla
    toplam_akts = sum(float(d[3]) for d in unique_dersler.values())

    if toplam_akts < 240:
        hatalar.append(f"Toplam AKTS {toplam_akts}, mezuniyet için en az 240 AKTS gereklidir.")

    # Aynı dersin birden fazla kez alınma kontrolü (uyarı için)
    ders_kodlari = [d[0] for d in dersler]
    if len(ders_kodlari) != len(set(ders_kodlari)):
        hatalar.append("Aynı ders birden fazla kez alınmış. Fazla alınan dersler kontrol edilmeli.")

    # Üniversite ve fakülte seçmeli kontrolü
    us_dersler = [d for d in unique_dersler.values() if d[0].startswith("US")]
    ms_dersler = [d for d in unique_dersler.values() if d[0].startswith("MS")]

    if len(us_dersler) < 1:
        hatalar.append("En az 1 üniversite seçmeli (US kodlu) ders alınmalıdır.")
    if len(ms_dersler) < 1:
        hatalar.append("En az 1 fakülte seçmeli (MS kodlu) ders alınmalıdır.")

    # Seçmeli ders kontrolü
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
        hatalar.append(f"Toplamda en az 10 seçmeli (BM kodlu) ders alınmalı. Şu an {len(secmeli_dersler)} tane var.")

    # Yaz stajı kontrolü
    yaz_staji_dersleri = [d for d in unique_dersler.values() if d[0] in ("BM399", "BM499")]
    if not yaz_staji_dersleri:
        hatalar.append("Yaz stajı (BM399 veya BM499) tamamlanmamış.")
    else:
        yaz_staji_yetersiz = any(d[4] == "YZ" for d in yaz_staji_dersleri)
        if yaz_staji_yetersiz:
            hatalar.append("Yaz stajı notu yetersiz (YZ).")

    # Başarısız ders kontrolü (bilgi amaçlı)
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
