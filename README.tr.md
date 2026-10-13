[English](README.md) | Türkçe

# KVKK Belge Asistanı

Türkçe kişisel veri içeren belgeler hakkında LLM'e soru sorun, ama bu veriyi modele göndermeden. Kişisel veriler bulunur, doğrulanır ve geri çevrilebilir takma adlarla değiştirilir; sunucudan yalnızca maskeli metin çıkar.

> Taslak: geliştirme sürüyor.

## Özellikler (MVP planı)
- `.txt`, `.pdf` veya `.docx` yükleme (en fazla 10 MB, yaklaşık 100 sayfa metin) ya da metin yapıştırma
- Doğrulamalı Türkçe tanıyıcılar: TCKN ve VKN (sağlama hanesi), IBAN (mod-97), kart numarası (Luhn), telefon, e-posta, plaka, ad-soyad
- Tutarlı takma adlarla önce/sonra görünümü (`[KISI_1]`); yanlış bulunan öğeyi tek tıkla çıkarma
- Belgeye soru sorma: maskeli parçalarda arama, kaynak gösteren cevap, takma adların yerelde geri konması
- Denetim kaydı: LLM'e tam olarak ne gittiği, token sayısı ve gecikme
- Gerçekçi sahte test verisi üretici (sağlaması geçerli TCKN/IBAN), değerlendirmede de kullanılır
- TR/EN, açık/koyu tema, istek sınırı, sıkı CSP; hiçbir şey saklanmaz (sadece bellek, 30 dk)

## Gelecek Planları
- Ad-soyad için Türkçe NER modeli, adres tanıma
- Kendi sunucusunda LLM seçeneği (Ollama)
