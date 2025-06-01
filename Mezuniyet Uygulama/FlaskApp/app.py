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
    """
    PDF'den çıkarılan metindeki (cid:XXX) formatındaki karakter kodlarını
    doğru Türkçe karakterlere dönüştürür.
    """
    if not isinstance(metin, str):
        return metin

    def degistir(match):
        cid_no = match.group(1)
        return cid_map.get(cid_no, '')

    temiz_metin = re.sub(r'\(cid:(\d+)\)', degistir, metin)
    return temiz_metin

def allowed_file(filename):
    """
    Yüklenen dosyanın izin verilen uzantılardan biri olup olmadığını kontrol eder.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_ders_bilgileri(pdf_path):
    """
    PDF'den ders bilgilerini (kod, ad, kredi, AKTS, harf notu) çıkarır.
    Bu fonksiyon, tüm derslerin AKTS'sini daha sonra toplamak için kullanılacak.
    """
    dersler = []
    with pdfplumber.open(pdf_path) as pdf:
        # Regex'i transkript formatınıza göre daha sağlam hale getirelim:
        # Ders kodu, ardından ders adı (boşluklar, Türkçe karakterler, tireler, noktalar ve yeni satırlar dahil)
        # sonra Kredi, AKTS ve Harf Notu.
        # Her bir grup arasında boşluklar (\s+) veya yeni satır (\n) olabilir.
        # Ders adındaki non-greedy (.*?) kullanıldı.
        # Harf notu için iki harfli kodlar veya YT/YZ.
        pattern = r"^(AIB\d{3}|BM\d{3}|FIZ\d{3}|ING\d{3}|MAT\d{3}|TDB\d{3}|KRP\d{3}|MS\d{3}|US\d{3}|SE\d{3})\s+([A-Za-zÇŞĞÜÖİçşğüöı\s\-\.]+?)\s+([\d.]+)\s+([\d.]+)\s+([A-F]{2}|YT|YZ)$"

        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines = text.split("\n")
                for line in lines:
                    cleaned_line = cid_temizle(line.strip()) # cid hatalarını temizle ve baştaki/sondaki boşlukları kaldır

                    match = re.search(pattern, cleaned_line)
                    if match:
                        ders_kodu = match.group(1).strip()
                        ders_ismi = match.group(2).strip()
                        kredi = match.group(3).strip()
                        akts = match.group(4).strip()
                        harf_notu = match.group(5).strip()

                        # Sayısal değerlerin geçerliliğini kontrol et
                        if kredi.replace('.', '').isdigit() and akts.replace('.', '').isdigit():
                            dersler.append((ders_kodu, ders_ismi, kredi, akts, harf_notu))
    return dersler

# extract_overall_akts fonksiyonu artık kullanılmayacak ve kaldırıldı.

def mezuniyet_hesapla(dersler): # overall_akts_from_pdf parametresi kaldırıldı
    """
    Mezuniyet şartlarını kontrol eder. Toplam AKTS, ders listesinden hesaplanır.
    """
    hatalar = []

    # Toplam AKTS kontrolü: Tüm derslerin AKTS'lerini topla
    toplam_akts = sum(float(ders[3]) for ders in dersler)

    if toplam_akts < 240:
        hatalar.append(f"Toplam AKTS {toplam_akts}, mezuniyet için en az 240 AKTS gereklidir.")

    # Aynı dersin birden fazla alınması kontrolü
    ders_kodlari = [ders[0] for ders in dersler]
    if len(ders_kodlari) != len(set(ders_kodlari)):
        hatalar.append("Aynı ders birden fazla kez alınmış. Fazla alınan dersler kontrol edilmeli.")

    # Üniversite seçmeli (US) ve Fakülte seçmeli (MS) ders kontrolü
    us_dersler = [d for d in dersler if d[0].startswith("US")]
    ms_dersler = [d for d in dersler if d[0].startswith("MS")]
    if len(us_dersler) < 1:
        hatalar.append("En az 1 üniversite seçmeli (US kodlu) ders alınmalıdır.")
    if len(ms_dersler) < 1:
        hatalar.append("En az 1 fakülte seçmeli (MS kodlu) ders alınmalıdır.")

    # Bölüm seçmeli ders kodları listesi
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

    secmeli_dersler = [d for d in dersler if d[0] in secmeli_ders_kodlari]

    if len(secmeli_dersler) < 10:
        hatalar.append(f"Toplamda en az 10 seçmeli (BM kodlu) ders alınmalı. Şu an {len(secmeli_dersler)} tane var.")

    # Yaz stajı kontrolü
    yaz_staji_dersleri = [d for d in dersler if d[0] in ("BM399", "BM499")]

    if not yaz_staji_dersleri:
        hatalar.append("Yaz stajı (BM399 veya BM499) tamamlanmamış.")
    else:
        # Transkriptinizde BM499 notu "YZ" olarak görünüyor.
        yetersiz_staj_ii = any(d[0] == "BM499" and d[4] == "YZ" for d in yaz_staji_dersleri)
        if yetersiz_staj_ii:
            hatalar.append("Yaz stajı II (BM499) notu yetersiz (YZ).")
        else:
            # BM399 veya BM499'dan herhangi biri YT veya başka geçer bir notla geçmeli
            if not any(d[4] == "YT" or (d[4] not in {"FF", "FD", "YZ"} and d[0] == "BM499") for d in yaz_staji_dersleri):
                hatalar.append("Yaz stajı (BM399 veya BM499) tamamlanmamış veya notu yetersiz.")

    # Başarısız ders kontrolü (FF, FD, YZ)
    basarisiz_notlar = {"FF", "FD", "YZ"}
    # Staj dersleri dışındaki başarısız dersleri bul
    basarisiz_dersler = [d for d in dersler if d[4] in basarisiz_notlar and d[0] not in ("BM399", "BM499")]

    if basarisiz_dersler:
        kodlar = ", ".join(set(d[0] for d in basarisiz_dersler))
        hatalar.append(f"Geçilemeyen ders(ler) var: {kodlar}")

    if not hatalar:
        return "Mezuniyet Şartları Sağlanıyor ✅"
    else:
        return "❌ Mezuniyet için eksikler:\n- " + "\n- ".join(hatalar)


@app.route("/")
def index():
    """Ana sayfa: PDF yükleme formu ve mezuniyet durumu gösterimi."""
    return render_template("index.html", mezuniyet_durumu=None)

@app.route("/upload", methods=["POST"])
def upload_pdf():
    """PDF yükleme ve mezuniyet kontrolü işlemini gerçekleştirir."""
    if 'pdf' not in request.files:
        return "Dosya seçilmedi.", 400

    pdf_file = request.files['pdf']

    if pdf_file and allowed_file(pdf_file.filename):
        filename = secure_filename(pdf_file.filename)
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        pdf_file.save(pdf_path)

        dersler = extract_ders_bilgileri(pdf_path) # Dersler her halükarda çekilecek

        if dersler: # Eğer dersler başarıyla çekilebildiyse devam et
            mezuniyet_durumu = mezuniyet_hesapla(dersler) # Genel AKTS parametresi kaldırıldı
            return render_template("index.html", mezuniyet_durumu=mezuniyet_durumu)
        else:
            return "PDF'den ders bilgileri bulunamadı. Lütfen dosyanızın metin içerdiğinden ve formatının desteklendiğinden emin olun.", 400

    return "Geçersiz dosya türü.", 400

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
