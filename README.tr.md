# KVKK Belge Asistanı

[English](README.md) | **Türkçe**

Türkçe kişisel veri içeren belgeler hakkında yapay zekâ modeline soru sorun, ama bu veriyi modele göndermeden. Ad-soyad, TCKN, vergi numarası, IBAN, kart numarası, telefon, e-posta ve plaka bulunur, doğrulanır ve `[KISI_1]` gibi takma adlarla değiştirilir. Sunucudan yalnızca maskeli metin çıkar; cevaptaki takma adlar sunucuda gerçek değerlerle geri değiştirilir.

**Canlı demo:** [kvkk.miracdeprem.com](https://kvkk.miracdeprem.com). Site ücretsiz bir sunucuda çalıştığı için bir süre kullanılmadıktan sonra ilk sayfa yarım dakika kadar gecikebilir.

![Maskeleme sonucu: kişisel verileri vurgulanmış orijinal belge ve modele giden maskeli metin yan yana](docs/screenshot-masking.png)

**Neden:** Şirketler büyük dil modellerini kullanmak istiyor ama kişisel veriyle dolu belgeler yurt dışındaki bir modele öylece gönderilemez (KVKK yurt dışına aktarımı şarta bağlar). Microsoft Presidio gibi hazır araçların Türkçe tanıyıcıları yok. Bu proje belgelerle model arasına Türkçe bir maskeleme katmanı koyuyor; bir şirket bunu kendi sunucusunda çalıştırır.

## Özellikler

**Kişisel veriyi bulma**
- Numaralar sadece biçimle eşleştirilmez, doğrulanır: TCKN ve VKN sağlama haneleri, IBAN mod-97, kart numarasında Luhn
- Her yaygın biçimde telefon numarası, e-posta, plaka (il kodu ve harf/rakam kuralları)
- Ad-soyadlar **benim eğittiğim bir modelle** bulunur: kişi, kurum ve yer tanımak için ince ayar yapılmış küçük bir Türkçe BERT; unvanlar ("Av.", "Sn.") ve etiketler ("Adı Soyadı:") için kurallarla birlikte çalışır
- Sahte ama geçerli verilerle demo belge üretici (sağlama haneleri geçer, hiçbiri gerçek bir kişiye ait değildir)

**Maskeleme**
- Aynı değer, nasıl yazılırsa yazılsın, her yerde aynı takma adı alır: `0532 123 45 67` ve `+90 532 123 45 67` ikisi de `[TELEFON_1]`, `AYŞE YILMAZ` ve `Ayşe Yılmaz` ikisi de `[KISI_1]`
- Önce/sonra görünümü; yanlış bulunan bir öğe tek tıkla maskeden çıkarılır
- `.txt`, `.pdf` veya `.docx` yükleme (en fazla 10 MB, yaklaşık 40 sayfa metin) ya da metin yapıştırma

**Soru sorma**
- Soru da aynı takma adlarla maskelenir; "gülfem kurtun telefonu" (küçük harf, bitişik ek) bile `[KISI_1]un telefonu` olur
- Uzun belgeler: maskeli parçalar vektörleştirilir ve en yakın olanlar gönderilir (RAG); kısa belgeler tamamen gönderilir
- Cevaplar kaynak alıntıları gösterir; isimler geri konurken Türkçe ekler düzeltilir ("Bulut'nin" → "Bulut'un")
- Denetim kaydı: sunucudan çıkan her istek, gönderildiği hâliyle; token sayısı, süre ve cevaplayan model

**Her yerde**
- Hiçbir şey saklanmaz: veritabanı yok, diske dosya yazılmaz; belge sadece bellekte durur ve 30 dakika kullanılmazsa silinir
- Türkçe ve İngilizce arayüz, açık ve koyu tema, telefonda çalışır

## Ekran Görüntüleri

| | |
|---|---|
| ![Üç adım ve yükleme formuyla ana sayfa](docs/screenshot-home.png) | ![Tür, değer ve takma adlarla bulunan veriler tablosu](docs/screenshot-findings.png) |
| ![Bir soru, gerçek değerlerle cevap ve modelin gerçekte gördüğü metin](docs/screenshot-ask.png) | ![Modele gönderilen maskeli metni birebir gösteren denetim kaydı](docs/screenshot-audit.png) |

![Koyu temada maskeleme sonucu](docs/screenshot-dark.png)

<p align="center"><img src="docs/screenshot-mobile.png" width="300" alt="Telefonda maskeleme sonucu"></p>

## Nasıl çalışır

```
belge ──► metin çıkarma ──► tanıma ────────────────────────► takma adlar ──► maskeli metin
          (txt, pdf, docx)  kurallar: numaralar + sağlama      [KISI_1]           │
                            model: kişi, kurum, yer            [TCKN_1]           │
                                                                                  ▼
soru ──► tanıma + belgedeki değerler ──► maskeli soru ──► ilgili parçalar ──► dil modeli
                                                                                  │
cevap ◄── takma adlar geri konur, ekler düzeltilir ◄── maskeli cevap ◄────────────┘
```

1. **Metin çıkarma.** Dosya türü sadece adından değil içeriğinden kontrol edilir. PDF metni Unicode NFC'den geçirilir; böylece "s + çengel" olarak saklanmış "ş" yeniden tek harf olur. `.docx` aslında bir zip dosyasıdır; açılmış boyutu önceden kontrol edilir (zip bombası).
2. **Tanıma.** Kurallar numaraları bulup sağlama hanelerini doğrular. İsim modeli metni satır sonlarında biten pencereler hâlinde okur. Model kullanıldığında, kuralların sadece sözlükten bulduğu isimler bırakılır (kararı model verir); unvan ya da etiketten sonra gelen isimler korunur.
3. **Maskeleme.** Her değer, her geçişinde aynı kalan bir takma ad alır. Takma addan gerçek değere giden tablo sunucudan hiç çıkmaz.
4. **Soru.** Soru aynı tabloyla maskelenir. Belgede zaten bulunmuş değerler soruda büyük/küçük harf, Türkçe karakter, bitişik ek ve ünsüz yumuşamasından ("Çeliğe") bağımsız olarak aranır.
5. **Cevap.** Önce Groq modelleri cevaplar (bir saniyenin altında); biri ücretsiz kotasını doldurmuş ya da yoğunsa sıradaki denenir, sonra Gemini modelleri. Vektörleştirme Gemini ile yapılır.

## İsim modeli

İlk sürüm isimleri sözlük ve kurallarla buluyordu. Elle yazılmış zor örneklerde sözlükte olmayan isimleri ve küçük harfle yazılanları kaçırıyor, "Umut Verici" gibi bir başlığı kişi sanıyordu. Bu yüzden bir model eğittim.

- **Veri:** WikiANN Türkçe (20.000 cümle) ve [`training/synth.py`](training/synth.py) ile üretilen 20.000 sentetik cümle: sözleşme, form, e-posta ve soru cümleleri; küçük harfle ya da Türkçe karakter olmadan yazılmış isimler, kesme işaretli ve bitişik ekler, isim içeren kurum ve yerler ("Deniz Yatırım A.Ş.", "Umut Mahallesi"). Değerlendirme setlerindeki isimler eğitimden çıkarıldı.
- **Eğitim:** [`training/train_ner.py`](training/train_ner.py), ücretsiz Google Colab GPU'sunda ([defter](training/train_ner.ipynb)); karışık hassasiyetli (mixed precision) düz bir PyTorch döngüsü, sonunda ONNX'e aktarım.
- **Boyut seçimi:** Ücretsiz sunucuda 0,1 CPU var, yani hız da doğruluk kadar önemliydi. Üç taban modeli eğitip ölçtüm; 11,5 milyon parametreli model tam hassasiyette (fp32) 66 milyonluk model kadar doğru ve 7 kat hızlı çıktı. int8 küçültme küçük modelin doğruluğunu düşürdüğü için fp32 çalışıyor. Ayrıntılar: [eval/model_comparison.md](eval/model_comparison.md).
- **Çalışma ortamı:** Sunucuda sadece `onnxruntime` ve `tokenizers` var, PyTorch yok. Model dosyası bir [GitHub Release](https://github.com/MrcDprm/kvkk-document-assistant/releases/tag/ner-model-v1)'e ekli; imaj oluşturulurken SHA-256 ile doğrulanıyor.

## Değerlendirme

`python -m eval.run_eval` sadece kuralları, sadece modeli ve ikisini birlikte karşılaştırır. Bir eşleşme ancak türü, başlangıcı ve bitişi birebir doğruysa sayılır. "Maskesiz kalan", maskelemeden sonra en az bir karakteri görünen etiketli değerdir. Tam çıktı: [eval/results.md](eval/results.md).

| Veri | Yöntem | İsim kesinliği | İsim yakalama | Maskesiz kalan değer |
|---|---|---|---|---|
| Sentetik belgeler (400) | Kurallar + model | 1,00 | 1,00 | 0 / 3800 |
| Zor örnekler (ayarda kullanıldı) | Kurallar | 0,81 | 0,77 | 5 / 35 |
| Zor örnekler (ayarda kullanıldı) | Kurallar + model | 1,00 | 1,00 | 0 / 35 |
| **Zor örnekler 2 (ayarda hiç kullanılmadı)** | Kurallar | 0,75 | **0,14** | 18 / 29 |
| **Zor örnekler 2 (ayarda hiç kullanılmadı)** | Kurallar + model | **1,00** | **1,00** | **0 / 29** |

İkinci zor örnek seti ayarlar bittikten sonra yazıldı ve hiçbir ayarda kullanılmadı. Küçük bir set (29 değer); kesin bir doğruluk oranından çok yönü gösteriyor.

## Kullanılan Teknolojiler

- **Python**, **FastAPI**, Jinja şablonları ve sade JavaScript (çatı yok, derleme adımı yok)
- Eğitim için **Hugging Face Transformers** ve **PyTorch** (sadece Colab'da); çalıştırma için **ONNX Runtime**
- **Groq** (gpt-oss-120b, Qwen3) ve **Google Gemini** (cevap ve vektörleştirme)
- Metin çıkarma için **pypdf**, **python-docx**
- **pytest** (600'den fazla test), **Render** üzerinde **Docker**

## Kurulum ve Çalıştırma

[kvkk.miracdeprem.com](https://kvkk.miracdeprem.com) adresini açın ya da Python 3.12 ile yerelde çalıştırın:

```bash
git clone https://github.com/MrcDprm/kvkk-document-assistant.git
cd kvkk-document-assistant
python -m venv .venv
.venv/Scripts/activate          # Windows; macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
```

İsteğe bağlı parçalar:

```bash
# isim modeli (yoksa isimler sadece kurallarla bulunur)
python scripts/fetch_model.py https://github.com/MrcDprm/kvkk-document-assistant/releases/download/ner-model-v1/kvkk-ner-model-v1.zip 463ea7aa9dc903b0338a2d168a8751e0f80f9c0db96926ab501474f4536eb50d models/ner

# soru sormak için API anahtarları: .env.example dosyasını .env olarak kopyalayıp GROQ_API_KEY ve/veya GEMINI_API_KEY doldurun
```

Uygulamayı çalıştırın (`COOKIE_SECURE=0` sadece kendi bilgisayarınızda düz http için gerekir):

```bash
COOKIE_SECURE=0 uvicorn app.main:app --reload --env-file .env
```

Sonra `http://127.0.0.1:8000` adresini açın. Testler ve değerlendirme:

```bash
pytest
python -m eval.run_eval
```

### Proje yapısı

```
kvkk_mask/        Maskeleme kütüphanesi (web kodu yok)
  validators.py   TCKN, VKN, IBAN ve Luhn sağlama haneleri
  recognizers.py  Numara, telefon, e-posta ve plaka kalıpları; çakışma çözümü
  names.py        Kural tabanlı isim: sözlük, unvan, etiket, Bey/Hanım
  ner.py          Eğitilmiş isim modeli (ONNX Runtime)
  known.py        Belgedeki değerleri soruda yeniden bulma
  pseudonymizer.py, suffix.py   Takma adlar, değerleri geri koyma, Türkçe ekler
  fakegen.py      Sahte ama geçerli veri ve demo belgeler
app/              FastAPI uygulaması: sayfalar, yükleme, soru-cevap, model sağlayıcıları, güvenlik
training/         Sentetik eğitim verisi, eğitim betiği, Colab defteri
eval/             Zor örnekler, değerlendirme betiği, sonuçlar ve model karşılaştırması
scripts/          SHA-256 kontrollü model indirme (Dockerfile'da kullanılır)
tests/            pytest testleri
```

### Güvenlik ve gizlilik

- Kişisel veri modele hiç ulaşmaz: belgeler ve sorular maskelenir; denetim kaydı tam olarak neyin gönderildiğini gösterir
- Diske ya da veritabanına hiçbir şey yazılmaz; yüklemeler bellekte kalır (Starlette'in diske taşırması kapatıldı), oturumlar 30 dakikada sona erer
- Oturum çerezi HttpOnly, Secure ve SameSite=Lax; kimlik 256 bitlik rastgele değer; başka sitelerden gelen POST istekleri reddedilir (Origin kontrolü)
- Sıkı Content Security Policy (sadece sitenin kendi betik ve stilleri, satır içi kod yok, üçüncü taraf istek yok), HSTS, `nosniff`, `Cache-Control: no-store`, CORS yok
- Yükleme kontrolleri: tür içerikten, boyut ayrıştırmadan önce, zip bombası kontrolü, XML varlıkları kapalı
- IP başına istek sınırı, alan adı izin listesi; kullanıcıya yığın izi ya da sağlayıcı hata mesajı gösterilmez
- Belgenin içindeki talimatlar veri olarak işlenir; bir model onlara uysa bile açığa çıkarabileceği gerçek kişisel veri yoktur
- API anahtarları sunucudaki ortam değişkenlerinde; `.env` git'e girmez

### Sınırlar

- Ne belgede geçen ne de modelin tanıyabildiği bir isim, soruda küçük harfle yazılırsa modele maskelenmeden gidebilir
- Adresler henüz tanınmıyor; taranmış (sadece görüntü olan) PDF'lerde okunacak metin yok
- Ücretsiz sunucu modelle saniyede yaklaşık 2.500 karakter işliyor; 40 sayfalık bir belge yaklaşık 40 saniye sürer
- WikiANN'in lisansı "unknown" olarak listeleniyor; sadece modeli eğitmek için kullanıldı ve yeniden dağıtılmıyor. Taban modelin sayfasında lisans belirtilmemiş

## Öğrendiklerim

- **Bir gizlilik aracı en zayıf girdisi kadar iyidir.** Testlerim geçiyordu ama canlı sitede "gülfem kurtun telefonu ne" diye sorduğumda isim modele maskelenmeden gitti: soruda "Adı Soyadı:" etiketi yoktu, küçük harfle yazılmıştı ve ek bitişikti. Belgedeki değerleri soruda da arayarak düzelttim, sonra her ismin 12.000 farklı yazımını deneyen sistematik bir test yazdım. Düzeltmeden önce bunların %67'si sızıyordu; sonra hiçbiri.
- **Önce ölçmek, sonra değiştirmek.** Model eğitmeden önce değerlendirme betiğini yazdım; böylece kuralların ayarda kullanılmamış bir sette isimlerin sadece %14'ünü bulduğunu, modelin hepsini bulduğunu görebildim. Hiç ayarlamadığım ikinci bir set tutmak sayıları dürüst kıldı.
- **Bir modeli eğitip yayına almak.** Kelime düzeyinde etiketler (IOB2) hazırladım, bunları alt kelimelerle hizaladım, BERT modellerini Colab GPU'sunda ince ayarladım ve sunucuda PyTorch gerekmesin diye ONNX'e aktardım.
- **Model boyutu bir ürün kararıdır.** 0,1 CPU'da en doğru model fazla yavaştı. Üç boyutu ve iki hassasiyeti karşılaştırdım; int8 büyük modele neredeyse hiç kaybettirmedi ama küçük modele zarar verdi, bu yüzden küçük modeli fp32 olarak yayına aldım.
- **Türkçe metnin kendi tuzakları var.** Python'un `lower()` fonksiyonu "I" harfini "ı" yerine "i" yapıyor, `capitalize()` "İrem" yerine "Irem" veriyor, PDF'ler "ş" harfini iki karakter olarak saklayabiliyor ve ekler ünlü uyumuna uyuyor. Her biri gerçek bir hataya yol açtı.
- **Ücretsiz katman bir üretim planı değildir.** Gemini 2.5 Flash günde 20 isteğe izin veriyor; başka bir model 10-35 saniye sürdü ya da "yoğun" cevabı verdi. Sağlayıcıları tek bir arayüzün arkasına koyup yedekli bir zincir kurdum; demo cevap vermeye devam ediyor.

## Teşekkür

- Taban model: [ytu-ce-cosmos/turkish-mini-bert-uncased](https://huggingface.co/ytu-ce-cosmos/turkish-mini-bert-uncased) (Kesgin vd., 2023)
- Eğitim verisi: [WikiANN](https://huggingface.co/datasets/unimelb-nlp/wikiann) (Pan vd., 2017; Rahimi vd., 2019)

## Lisans

[MIT](LICENSE)
