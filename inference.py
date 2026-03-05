import pickle
import os
import re
import fitz
import argparse
import sys

def load_sbd_model(model_path="contract_sbd.pickle"):
    """Eğitilen Punkt modelini yükler."""
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"'{model_path}' bulunamadı. Lütfen önce 'python train_model.py' scriptini çalıştırarak modeli eğitin.")
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    return model

def preprocess_text(text):
    """Noktalama maskelemelerini gerçekleştirir."""
    # 1. "Madde 1.", "Madde 2.1." şeklindeki başlıkları gizle
    text = re.sub(r'(?i)(Madde\s+\d+(?:\.\d+)*)\.(?=\s)', r'\1<DOT>', text)
    
    # 2. "1.", "2.1.", "3.1.2." gibi madde numaralarını gizle
    text = re.sub(r'\b(\d+(?:\.\d+)*)\.(?=\s)', r'\1<DOT>', text)
    
    # 3. İsteğe bağlı: Tek büyük harf ile başlayan maddeler "A.", "B." veya Roma rakamları
    text = re.sub(r'\b([A-ZŞİĞÜÖÇ]|[ivxlcdm]+)\.(?=\s)', r'\1<DOT>', text, flags=re.IGNORECASE)
    
    # 4. Noktadan sonra sadece AYNI SATIRDA boşluk ve KÜÇÜK harf geliyorsa noktayı gizle
    text = re.sub(r'(\S+)\.(?=[ \t]+[a-zçğıöşü])', r'\1<DOT>', text)
    
    # 5. a), b), f), 1) gibi satır başında başlayan alt bentleri bağımsız cümle/paragraf yapmak için, 
    # Punkt modelinin mutlak ayrım olarak anladığı "\n\n" yani çift satır sonunu ekliyoruz.
    text = re.sub(r'\n([ \t]*(?:[a-zA-ZçğıöşüÇĞİÖŞÜ]{1,3}|\d+(?:\.\d+)*)[.)]\s)', r'\n\n\1', text)
    
    # 6. "MADDE 1-" gibi başlıkları önceki başlıklardan veya paragraflardan kesin olarak ayırmak için:
    text = re.sub(r'\n([ \t]*(?i:MADDE)\s+\d+)', r'\n\n\1', text)
    
    return text

def postprocess_sentences(sentences):
    """Maskelenen noktaları geri döndürür."""
    return [s.replace('<DOT>', '.') for s in sentences]

def split_into_sentences(text, model=None):
    """Verilen metni cümlelere ayırır."""
    if not text or not text.strip():
        return []
        
    if model is None:
        model = load_sbd_model()
            
    processed_text = preprocess_text(text)
    
    # Paragrafları (çift satır sonu) veya görsel blokları kesin ayrım olarak kabul ediyoruz.
    # (Özellikle virgülle veya noktalı virgülle biten sözleşme maddelerini Punkt modelinin birleştirmesini engeller)
    paragraphs = re.split(r'\n\s*\n', processed_text)
    
    all_sentences = []
    for para in paragraphs:
        if not para.strip():
            continue
        para_sentences = model.tokenize(para)
        all_sentences.extend(para_sentences)
        
    sentences = postprocess_sentences(all_sentences)
    
    return sentences

def process_pdf(pdf_path, model=None):
    """Bir PDF dosyasını okuyarak sayfa sayfa böler ve metni ayıklar."""
    if model is None:
        model = load_sbd_model()
        
    doc = fitz.open(pdf_path)
    results = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # İçindekiler ve Footer gibi kısımları bozmamak için görsel okuma:
        blocks = page.get_text("blocks")
        text_blocks = [b for b in blocks if b[6] == 0]
        
        # Yukarıdan aşağıya yatay hat oluşturacak şekilde (Y koordinatı) ve Soldan Sağa sırala
        text_blocks.sort(key=lambda b: (round(b[1]), b[0]))
        
        # Sayfanın doğal yapısını (kopuk kelimeleri) birleştirmek için blokları standart yeni satırla uc uca ekle
        # Bu işlem footer'ı en sona iterken, İçindekiler gibi sütunları sırasıyla listeler.
        text = "\n".join([b[4].strip() for b in text_blocks])
        
        if not text.strip():
            results.append({
                "page": page_num + 1,
                "raw_text": "",
                "sentences": []
            })
            continue
            
        sentences = split_into_sentences(text, model)
        results.append({
            "page": page_num + 1,
            "raw_text": text,
            "sentences": sentences
        })
        
    doc.close()
    return results

def main():
    parser = argparse.ArgumentParser(description="PDF üzerinden sözleşme/hukuk cümle bölücü.")
    parser.add_argument("-f", "--file", type=str, help="İşlenecek PDF dosyasının yolu", required=True)
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Hata: '{args.file}' dosyası bulunamadı.")
        sys.exit(1)

    print(f"'{args.file}' işleniyor...")
    
    try:
        model = load_sbd_model()
        results = process_pdf(args.file, model)
        
        with open("output.txt", "w", encoding="utf-8") as out:
            out.write(f"--- {os.path.basename(args.file)} Analizi ---\n\n")
            
            for res in results:
                out.write(f"=== SAYFA {res['page']} ===\n")
                out.write("--- Ham Metin ---\n")
                out.write(res['raw_text'].strip() + "\n\n")
                out.write("--- Cümlelere Ayrılmış Hali ---\n")
                
                if not res['sentences']:
                    out.write("(Okunabilir metin yok)\n")
                else:
                    for i, s in enumerate(res['sentences'], 1):
                        out.write(f"Cümle {i}:\n{s.strip()}\n\n")
                out.write("\n" + "="*40 + "\n\n")
                
        print("İşlem tamamlandı! Sonuçlar 'output.txt' dosyasına kaydedildi.")
        
    except Exception as e:
        print(f"Bir hata oluştu: {e}")

if __name__ == "__main__":
    main()
