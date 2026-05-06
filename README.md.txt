# Excel Kayıt Birleştirme Aracı (Upsert Data App)

Bu proje, Streamlit ve Pandas kullanılarak geliştirilmiş bir web uygulamasıdır. Her ay sisteme yüklenen yeni kayıt Excel dosyaları ile eski ana (master) Excel dosyasını akıllı bir şekilde birleştirir.

## 🛠️ Teknik Özellikler

- **Koşullu Eşleştirme:** Kayıtlar `İTİRAZ KONUSU KİŞİNİN ADI SOYADI` ve `İTİRAZ KONUSU KİŞİNİN TC KİMLİK NO` kolonlarına göre eşleştirilir.
- **Veri Tamamlama (Coalesce):** Eşleşen kayıtlarda eski satır silinir, yeni satır geçerli sayılır. Ancak yeni satırda eksik/boş bırakılmış hücreler varsa, veri kaybını önlemek adına bu boşluklar eski satırdaki verilerle doldurulur.
- **Hata Kontrolü:** 11 haneli olmayan veya harf içeren hatalı TC Kimlik numaraları tespit edilir ve arayüzde kullanıcıya uyarı verilir.
- **Metrik Gösterimi:** İşlem sonucunda kaç kaydın sıfırdan eklendiği ve kaç kaydın güncellendiği ekrana yansıtılır.

## 🚀 Kurulum Adımları

1. Repoyu bilgisayarınıza klonlayın veya indirin:
   ```bash
   git clone <repo_url>
   cd <repo_directory>