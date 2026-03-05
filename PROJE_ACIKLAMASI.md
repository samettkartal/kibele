# Türkçe Hukuk ve Sözleşme Metinleri İçin Cümle Bölücü (SBD) Projesi

Bu proje, Türkçe sözleşmelerde ve hukuki metinlerde çokça karşılaşılan zorlu cümle yapılarını (Örn: `Madde 1.`, `T.A.Ş.`, `Av. Dr.`, tarih ve parasal tutarlar) kusursuz bir şekilde cümlelere ayıran (Sentence Boundary Detection - SBD) tamamen özel bir **Makine Öğrenmesi (NLP)** hattıdır.

Ağır ve yavaş çalışan Derin Öğrenme (GPT vb.) modelleri veya yüzlerce satırlık karmaşık Regex kuralları yerine; oldukça hafif, istatistiksel ve kararlı çalışan **NLTK Punkt** algoritması tercih edilmiştir.

---

## Proje Aşamaları ve Mantığı

Projemiz genel olarak 3 temel aşamadan (dosyadan) oluşmaktadır:

### 1. Sentetik Veri Üretimi (`generate_data.py` ve `generate_edge_cases.py`)
NLTK Punkt algoritması, kelimelerin ve noktalamaların frekansını **metinlerden okuyarak istatistiksel yollarla öğrenir**. Türkçe hukuki metinlerde modeli eğitebilmek için devasa bir veri setine ihtiyacımız vardı.

* **Ne Yaptık:** Gemini Yapay Zeka API'sine çok detaylı Prompt'lar (komutlar) yolladık.
* **Nasıl Bir Veri Hazırladık:** Klasik cümleler yerine modeli zorlayacak, noktanın cümlenin sonu *olmadığını* kanıtlayacak metinler ürettik:
  * "T.A.Ş. ile ...", "Ltd. Şti. olarak..." gibi şirketin kısaltmalarının ortada olduğu cümleler.
  * "Madde 2.1. ve 3.2.1. uyarınca..." gibi sayısal bentler.
  * Tarihler (`01.01.2026`) ve ondalık sayılar (`1.500.000,00 USD`).
* **Overfitting (Aşırı Ezber) Koruması:** Punkt bir derin öğrenme (Deep Learning) mekanizması olmadığı için verinin artması sorun değil, **avantajdır**. Tamamen istatistiksel çalıştığı için ona yaklaşık **3000 paragraflık (synthetic_corpus.txt)** farklı kelime gruplarından oluşan bir korpus (veri havuzu) sunduk.

### 2. İstatistiksel Model Eğitimi (`train_model.py`)
* **Ne Yaptık:** Hazırladığımız bu 3000 satırlık zorlu hukuk/sözleşme veri setimizi `NLTK PunktTrainer` algoritmasına verdik.
* **Ekstra Güvence:** Punkt algoritmasına `T.C.`, `Av.`, `Sic.`, `Tic.` gibi hukukta sık kullanılan kısaltmaları manuel olarak (`abbrev_types`) ekledik. Öğrenme işlemi bittikten sonra çıkan şablonu **`contract_sbd.pickle`** isimli 1MB'dan bile küçük bir "hafif model" dosyası olarak kaydettik.

### 3. Cümle Bölme (Inference) ve Maskeleme (`inference.py`)
Artık modelimiz hukuk metinlerini okuyabiliyor, tarihlerin veya "T.A.Ş." gibi kısaltmaların cümle sonu olmadığını anlıyordu. Ancak **"Madde 1."** veya **"ABD. ve Avrupa ülkeleri"** gibi dünya üzerindeki her modelin (ChatGPT dahi) kafasını karıştıran evrensel sorunlar kalmıştı.

Bu sorunları NLP dünyasının en kalıcı çözümü olan **Pre-processing (Ön İşleme / Maskeleme)** ile çözdük.

* **Maskeleme (Masking) Nedir?**
  Metin Punkt modeline girmeden hemen önce, bir Python `Regex` kodu bütün metni saniyeler içinde tarar ve şu tuzaklı kısımları bulur:
  1. Başlıklar ve madde numaraları (Örn: `Madde 1.`, `2.1.`, `iv.`).
  2. Noktadan sonra **küçük harf** ile devam eden kısaltmalar (Örn: `T.A.Ş. ile`, `ABD. ve`). Noktadan sonra küçük harf geliyorsa bu kesinlikle yeni bir cümle olamaz!
  
* **Nasıl Çalışır:**
  Python, bu tuzak noktalara `<DOT>` adında gizli bir etiket yapıştırır (Örn: `Madde 1<DOT>`).
  Model bu metne baktığında noktayı göremez, dolayısıyla cümleyi **asla bölmez.** Model metni cümlelere cillop gibi ayırdıktan sonra, en sonda o `<DOT>` etiketleri eski gerçek noktalara (`.`) dönüştürülür ve kullanıcıya sorunsuz çıktı verilir.

* **Sayfa Sayfa İşleme (Chunking):**
  Devasa uzunluğundaki sözleşmelerin modeli fazla yormasını, hızını düşürmesini ve özellikle noktalama izleme performansında sapıtmasını engellemek için metinler bütün halinde değil; paragraf bütünlüğü korunarak "sayfa sayfa" (belirli bir karakter limitine bölünerek) modele aktarılır. Bu sayede hem performanslı çalışılır hem de doğruluk (accuracy) en üst seviyede kalır.

---

## Sonuç
Bu sistem sayesinde, ne her sözcük için yüzlerce satır karmaşık kuralı elle yazmanız (Regex Spagettisi) gerekir, ne de her cümleyi bölmek için maliyetli yapay zekalara (LLM) ihtiyaç duyarsınız. Sistemin kalbi istatistik (`Punkt`) ile, kasları evrensel kurallar (`Maskeleme`) ile korunan, hem sözleşmelerde hem de gazete metinlerinde devasa bir hızla (bilgisayarı yormadan) çalışan yerel ve kalıcı bir API altyapınız oluştu.
