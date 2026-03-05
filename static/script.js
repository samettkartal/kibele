document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const loading = document.getElementById('loading');
    const resultsContainer = document.getElementById('results-container');
    const rawTextBox = document.getElementById('raw-text-box');
    const sentencesBox = document.getElementById('sentences-box');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const pageIndicator = document.getElementById('page-indicator');
    const newDocBtn = document.getElementById('new-doc-btn');

    let pdfData = [];
    let currentPage = 0;

    // Tıklayarak yükleme
    dropZone.addEventListener('click', () => fileInput.click());

    // Sürükle Bırak ayarları
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) {
            handleFile(e.target.files[0]);
        }
    });

    function handleFile(file) {

        const formData = new FormData();
        formData.append('file', file);

        dropZone.classList.add('hidden');
        resultsContainer.classList.add('hidden');
        loading.classList.remove('hidden');

        fetch('/api/upload', {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                loading.classList.add('hidden');
                if (data.error) {
                    alert(data.error);
                    dropZone.classList.remove('hidden');
                } else {
                    pdfData = data.results;
                    if (pdfData.length > 0) {
                        currentPage = 0;
                        renderPage();

                        if (data.legislation_info) {
                            displayLegislationInfo(data.legislation_info);
                        }

                        resultsContainer.classList.remove('hidden');
                    } else {
                        alert('PDF boş veya okunamadı.');
                        dropZone.classList.remove('hidden');
                    }
                }
            })
            .catch(err => {
                loading.classList.add('hidden');
                alert('Bir hata oluştu: ' + err.message);
                dropZone.classList.remove('hidden');
            });
    }

    function renderPage() {
        const pageData = pdfData[currentPage];

        // Ham metin kısmı
        rawTextBox.textContent = pageData.raw_text;

        // Cümleler kısmı
        sentencesBox.innerHTML = '';
        if (pageData.sentences.length === 0) {
            sentencesBox.innerHTML = '<p style="color: gray;">Bu sayfada okunabilir metin bulunamadı.</p>';
        } else {
            pageData.sentences.forEach((sentence, index) => {
                const div = document.createElement('div');
                div.className = 'sentence-item';
                div.innerHTML = `<span class="sentence-index">${index + 1}.</span> ${sentence}`;
                sentencesBox.appendChild(div);
            });
        }

        // Navigasyon kontrolleri
        pageIndicator.textContent = `Sayfa ${currentPage + 1} / ${pdfData.length}`;
        prevBtn.disabled = currentPage === 0;
        nextBtn.disabled = currentPage === pdfData.length - 1;

        // Scroll'u sıfırla
        rawTextBox.scrollTop = 0;
        sentencesBox.scrollTop = 0;
    }

    prevBtn.addEventListener('click', () => {
        if (currentPage > 0) {
            currentPage--;
            renderPage();
        }
    });

    nextBtn.addEventListener('click', () => {
        if (currentPage < pdfData.length - 1) {
            currentPage++;
            renderPage();
        }
    });

    newDocBtn.addEventListener('click', () => {
        resultsContainer.classList.add('hidden');
        dropZone.classList.remove('hidden');
        fileInput.value = ''; // Dosya seçimini sıfırla
        pdfData = [];
        currentPage = 0;
    });

    function displayLegislationInfo(info) {
        const card = document.getElementById('legislation-info');
        card.className = 'legislation-card'; // sıfırla

        // Renk Kodlaması: EXACT/HIGH = Yeşil, FUZZY = Sarı, NO_MATCH = Kırmızı
        if (info.status === 'MATCH_FOUND') {
            card.classList.add('status-success');
            let txt = `<h3>✅ Doğrudan Mevzuat Eşleşti</h3>`;
            txt += `<p><strong>${info.message}</strong></p>`;
            txt += `<p>Bulunan Mevzuatlar: <span class="badge highlight">${info.legislations_found.join("</span> <span class='badge highlight'>")}</span></p>`;

            if (info.details && info.details.length > 0) {
                txt += `<div class="details-section">
                            <h4>🔍 Eşleşme Detayları (${info.details.length} Tespit)</h4>`;

                info.details.forEach(item => {
                    const urlStr = item.mevzuat_url ? `<a href="${item.mevzuat_url}" target="_blank" class="url-link">🔗 İncele</a>` : '';
                    const keywordStr = item.keyword ? `<span class="badge key">${item.keyword}</span>` : '';

                    const isFuzzy = item.type === 'fuzzy_prediction';
                    const typeLabel = isFuzzy
                        ? `<span class="badge warning">⚠️ Fuzzy Tahmin &nbsp;%${item.score}</span>`
                        : `<span class="badge highlight">✅ Kesin Eşleşme</span>`;

                    const itemClass = isFuzzy ? 'detail-item detail-item--fuzzy' : 'detail-item';

                    txt += `<div class="${itemClass}">
                                <p><strong>Anahtar Kelime:</strong> ${keywordStr} &nbsp; ${typeLabel}</p>
                                <p><strong>Tespit Edilen Mevzuat:</strong> ${item.mevzuat} ${urlStr}</p>
                                <p class="sentence-text">"${item.cumle}"</p>
                            </div>`;
                });
                txt += `</div>`;
            }
            card.innerHTML = txt;
        }
        else if (info.status === 'DOCUMENT_FUZZY_MATCH') {
            card.classList.add('status-warning');
            const urlStr = info.mevzuat_url ? `<a href="${info.mevzuat_url}" target="_blank" class="url-link">🔗 İncele</a>` : '';
            const keywordStr = info.keyword ? `<span class="badge key">${info.keyword}</span>` : '';
            const sentenceStr = info.best_sentence ? `"${info.best_sentence}"` : '"Cümle bazlı cımbızlama tespit edilemediğinden, metnin geneline bakılmıştır."';
            card.innerHTML = `
                <h3>⚠️ Kısmi Eşleşme Tahmini (Döküman Geneli)</h3>
                <p><strong>${info.message}</strong></p>
                
                <div class="details-section">
                    <h4>🔍 Modifiye Edilmiş Bulanık Arama Tahmini</h4>
                    <div class="detail-item">
                        <p><strong>Anahtar Kelime:</strong> ${keywordStr}</p>
                        <p><strong>En Yakın Mevzuat:</strong> ${info.mevzuat_tahmini} ${urlStr}</p>
                        <p><strong>Uyum Skoru:</strong> <span class="badge warning">%${info.score}</span></p>
                        <p class="sentence-text">${sentenceStr}</p>
                    </div>
                </div>
            `;
        }
        else {
            card.classList.add('status-error');
            card.innerHTML = `
                <h3>❌ Sonuç Bulunamadı</h3>
                <p><strong>${info.message}</strong></p>
                <p>Metin analiz edildi ancak Şirket Veritabanında (MSSQL) ilişkili bir kanun bulunamadı.</p>
            `;
        }
    }
});
