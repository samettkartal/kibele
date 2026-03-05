import os
import re
import pyodbc
from thefuzz import process, fuzz
from dotenv import load_dotenv


class LegislationMatcher:
    def __init__(self):        
        load_dotenv()
        self.dbConnStr = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            f"SERVER={os.getenv('DB_SERVER')};"
            f"DATABASE={os.getenv('DB_NAME')};"
            f"UID={os.getenv('DB_USER')};"
            f"PWD={os.getenv('DB_PASSWORD')};"
        )
        print("Db bağlandı")
        self.keywords = [
            r"kanun\w*", r"yasa", r"yasas\w*", r"yasay\w*", r"yasad\w*",
            r"yasan\w*", r"yasal\w*", r"yasam\w*", r"anayas\w*",
            r"yönetmeli[kğ]\w*", r"kararname\w*", r"tebliğ\w*",
            r"tüzü[kğ]\w*", r"mevzuat\w*"
        ]

        self.legislationsFromDb = []
        self.normalizedLegislations = {}

        self.legislationsDict = {}
        self.legislationsByLength = {}
        self.normalizedLegislationsCache = []


    def normalizeText(self, text):
        if not text:
            return ""

        normalizedText = text.replace("I", "ı").replace("İ", "i")
        normalizedText = normalizedText.lower()
        normalizedText = re.sub(r"[''][a-zçğıöşü]+", "", normalizedText)
        normalizedText = re.sub(r"[^\w\s]", " ", normalizedText)
        normalizedText = re.sub(r"\s+", " ", normalizedText).strip()
        return normalizedText

    def isValidMatch(self, sentence, mevzuat_name):
        generics = ["kanun", "yasa", "anayas", "yönetmeli", "tüzü", "kararname", "tebliğ", "mevzuat",
                "dair", "hakkında", "ilişkin", "ve", "ile", "hükm", "bazı", "yapılmas", "değişiklik", "esasına", "esaslarına", "kanunu", "yönetmelik", "hakkinda"]

        m_words = self.normalizeText(mevzuat_name).split()

        distinctive_m_words = []
        for w in m_words:
            is_generic = False
            for g in generics:
                if g in ["ve", "ile", "bazı", "dair", "veya", "yahut"]:
                    if w == g:
                        is_generic = True
                        break
                else:
                    if w.startswith(g) or w == g:
                        is_generic = True
                        break
            if not is_generic:
                distinctive_m_words.append(w)

        if not distinctive_m_words:
            return True

        s_words = self.normalizeText(sentence).split()
        match_count = 0

        for dw in distinctive_m_words:
            matched_dw = False
            for sw in s_words:
                if fuzz.ratio(dw, sw) >= 70 or (len(dw) >= 4 and (dw in sw or sw in dw)):
                    matched_dw = True
                    break
            if matched_dw:
                match_count += 1

        required_match = 1
        if len(distinctive_m_words) >= 4:
            required_match = 2

        return match_count >= required_match

    def fetchLegislationsFromDb(self):
        query = "SELECT url, mevAdi FROM dbo.mevzuat_metadata WITH(NOLOCK) WHERE mevAdi IS NOT NULL"
        try:
            conn = pyodbc.connect(self.dbConnStr, readonly=True, autocommit=True)
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()

            self.legislationsDict = {}
            self.legislationsByLength = {}
            self.normalizedLegislationsCache = []

            for row in rows:
                rowUrl = row[0]
                if rowUrl and not rowUrl.startswith("http"):
                    rowUrlCleaned = rowUrl.lstrip("/")
                    rowUrl = f"https://www.mevzuat.gov.tr/{rowUrlCleaned}"

                legislationName = str(row[1]).strip()
                if not legislationName:
                    continue

                self.legislationsDict[legislationName] = rowUrl

                normalizedLegislationName = self.normalizeText(legislationName)
                if not normalizedLegislationName:
                    continue

                legislationWords = normalizedLegislationName.split()
                wordCount = len(legislationWords)

                if wordCount not in self.legislationsByLength:
                    self.legislationsByLength[wordCount] = {}

                self.legislationsByLength[wordCount][normalizedLegislationName] = {
                    "original": legislationName,
                    "url": rowUrl
                }

                self.normalizedLegislationsCache.append({
                    "original": legislationName,
                    "normalized": normalizedLegislationName,
                    "wordsSet": set(legislationWords),
                    "url": rowUrl
                })

            print(f"DB'den {len(self.legislationsDict)} adet mevzuat başarıyla çekildi.")
            print("Sözlük yapısı (Hash Table) oluşturuldu.")

        except Exception as e:
            print(f"[HATA] DB Bağlantı / Çekme Hatası: {e}")
            self.legislationsDict = {}
            self.legislationsByLength = {}
            self.normalizedLegislationsCache = []

    def filterSentences(self, sentences):
        keywordPattern = re.compile(r"\b(" + "|".join(self.keywords) + r")\b", re.IGNORECASE)
        filteredSentences = []

        for sentence in sentences:
            matches = keywordPattern.findall(sentence)
            if matches:
                found_keywords = list(set([m.lower() for m in matches]))
                keyword_str = ", ".join(found_keywords)

                filteredSentences.append({
                    "text": sentence,
                    "keyword": keyword_str,
                    "keywords_list": found_keywords
                })

        return filteredSentences

    def findMatchesInSentences(self, filteredSentences):
        matches = []

        for sentenceItem in filteredSentences:
            sentenceText = sentenceItem["text"]
            keyword = sentenceItem["keyword"]

            normalizedSentence = self.normalizeText(sentenceText)
            sentenceWords = normalizedSentence.split()
            sentenceWordCount = len(sentenceWords)
            sentenceWordsSet = set(sentenceWords)

            foundExact = False

            for windowLength, legislationMap in self.legislationsByLength.items():
                if windowLength > sentenceWordCount or windowLength == 0:
                    continue

                for i in range(sentenceWordCount - windowLength + 1):
                    windowText = " ".join(sentenceWords[i:i + windowLength])

                    if windowText in legislationMap:
                        legislationInfo = legislationMap[windowText]
                        originalLegislation = legislationInfo["original"]
                        legislationUrl = legislationInfo["url"]

                        legislationPreview = (
                            originalLegislation[:100] + "..."
                            if len(originalLegislation) > 100
                            else originalLegislation
                        )

                        matches.append({
                            "mevzuat": legislationPreview,
                            "mevzuat_url": legislationUrl,
                            "cumle": sentenceText,
                            "keyword": keyword,
                            "type": "exact_sliding_window"
                        })

                        foundExact = True

            if not foundExact:
                if sentenceWordCount > 200:
                    continue

                for legislationItem in self.normalizedLegislationsCache:
                    legislationWordsSet = legislationItem["wordsSet"]
                    overlapWords = legislationWordsSet & sentenceWordsSet

                    if len(overlapWords) > 0 and len(overlapWords) >= len(legislationWordsSet) / 2:
                        score = fuzz.partial_ratio(legislationItem["normalized"], normalizedSentence)

                        if score >= 95:
                            originalLegislation = legislationItem["original"]
                            legislationUrl = legislationItem["url"]

                            legislationPreview = (
                                originalLegislation[:100] + "..."
                                if len(originalLegislation) > 100
                                else originalLegislation
                            )

                            matches.append({
                                "mevzuat": legislationPreview,
                                "mevzuat_url": legislationUrl,
                                "cumle": sentenceText,
                                "keyword": keyword,
                                "type": "high_confidence_fuzzy",
                                "score": score
                            })

        return matches

    def get_keyword_windows(self, sentenceText, keywords_list, window_size=6):
        words = sentenceText.split()
        windows = []
        for kw in keywords_list:
            kw_lower = kw.lower()
            for i, w in enumerate(words):
                if kw_lower in w.lower():
                    start = max(0, i - window_size)
                    end = min(len(words), i + window_size + 1)
                    windows.append(" ".join(words[start:end]))
        unique_windows = list(dict.fromkeys(windows))
        return unique_windows if unique_windows else [sentenceText]

    def get_fuzzy_matches(self, sentences):
        if not self.legislationsDict:
            return [], 0

        matches = []
        max_score = 0

        unique_sentences = {}
        for sentenceItem in sentences:
            unique_sentences[sentenceItem["text"]] = sentenceItem.get("keywords_list", [sentenceItem.get("keyword", "")])

        keyword_roots = ["kanun", "yasa", "anayas", "yönetmeli", "kararname", "tebliğ", "tüzü", "mevzuat"]

        for sentenceText, keywords_list in unique_sentences.items():
            valid_roots = set()
            for kw in keywords_list:
                kw_lower = kw.lower()
                matched_root = kw_lower

                for r in keyword_roots:
                    if r in kw_lower:
                        matched_root = r
                        break
                valid_roots.add(matched_root)

            use_full_list = "mevzuat" in valid_roots

            candidates_set = set()
            if not use_full_list:
                for r in valid_roots:
                    for item in self.normalizedLegislationsCache:
                        if r in item["normalized"]:
                            candidates_set.add(item["original"])

            if use_full_list or not candidates_set:
                candidates = list(self.legislationsDict.keys())
            else:
                candidates = list(candidates_set)

            search_texts = self.get_keyword_windows(sentenceText, keywords_list)

            best_per_candidate = {}

            for window in search_texts:
                results = process.extract(
                    window,
                    candidates,
                    scorer=fuzz.token_set_ratio,
                    limit=5
                )

                for res in results:
                    matchedName = res[0]
                    score = res[1]

                    if score >= 65:
                        if self.isValidMatch(sentenceText, matchedName):
                            prev_score = best_per_candidate.get(matchedName, 0)
                            if score > prev_score:
                                best_per_candidate[matchedName] = score

            for matchedName, score in best_per_candidate.items():
                if score > max_score:
                    max_score = score

                matches.append({
                    "mevzuat": matchedName,
                    "score": score,
                    "cumle": sentenceText,
                    "keyword": ", ".join(keywords_list)
                })

        return sorted(matches, key=lambda x: x["score"], reverse=True), max_score

    def analyze(self, sentences):
        filteredSentences = self.filterSentences(sentences)
        sentenceMatches = self.findMatchesInSentences(filteredSentences)

        matched_sentences = {m["cumle"] for m in sentenceMatches}
        unmatched_sentences = [s for s in filteredSentences if s["text"] not in matched_sentences]

        fuzzy_matches, max_fuzzy_score = self.get_fuzzy_matches(unmatched_sentences)

        for fm in fuzzy_matches:
            original_name = fm["mevzuat"]
            preview = original_name[:100] + "..." if len(original_name) > 100 else original_name
            url = self.legislationsDict.get(original_name, "")

            sentenceMatches.append({
                "mevzuat": preview,
                "mevzuat_url": url,
                "cumle": fm["cumle"],
                "keyword": fm["keyword"],
                "type": "fuzzy_prediction",
                "score": fm["score"]
            })

        if len(sentenceMatches) > 0:
            foundLegislations = list({m["mevzuat"] for m in sentenceMatches})
            has_exact = any(m.get("type") in ["exact_sliding_window", "high_confidence_fuzzy"] for m in sentenceMatches)

            if has_exact:
                return {
                    "status": "MATCH_FOUND",
                    "message": "Metin içerisinde DB'deki Mevzuat isimleri doğrudan yakalandı ve/veya fuzzy tahminler eklendi.",
                    "filtered_sentences_count": len(filteredSentences),
                    "legislations_found": foundLegislations,
                    "details": sentenceMatches
                }
            else:
                best_fuzzy = fuzzy_matches[0]
                preview = best_fuzzy["mevzuat"][:100] + "..." if len(best_fuzzy["mevzuat"]) > 100 else best_fuzzy["mevzuat"]
                return {
                    "status": "DOCUMENT_FUZZY_MATCH",
                    "message": f"Tam eşleşme yok. Ancak filtrelenmiş cümle(ler) ile veritabanındaki kayıt %{best_fuzzy['score']} oranında uyuşuyor.",
                    "filtered_sentences_count": len(filteredSentences),
                    "mevzuat_tahmini": preview,
                    "mevzuat_url": self.legislationsDict.get(best_fuzzy["mevzuat"], ""),
                    "score": best_fuzzy["score"],
                    "best_sentence": best_fuzzy["cumle"],
                    "keyword": best_fuzzy["keyword"],
                    "details": sentenceMatches
                }

        return {
            "status": "NO_MATCH",
            "message": f"Mevzuat tespit edilemedi (Fuzzy Skoru eşiğin altında: %{max_fuzzy_score}). Veritabanı ile eşleşen bir sonuç bulunamadı.",
            "filtered_sentences_count": len(filteredSentences),
            "fuzzy_score_was": max_fuzzy_score
        }