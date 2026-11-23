# OpsPilot AI

**Akıllı Müşteri Destek ve İade Süreci Asistanı** — BTK Akademi Yapay Zekâ Çözümleri Kariyer Geliştirme Atölyesi bitirme projesi.

Destek uzmanına gelen iade, garanti, kargo ve şikâyet taleplerini şirket politikaları üzerinden **yerel RAG** ile analiz eder; ilgili maddeyi **kaynak göstererek** öneri ve müşteri yanıt taslağı hazırlar. **Son kararı her zaman çalışan verir** (human-in-the-loop). Tüm modeller yerelde (Ollama) çalışır; müşteri verisi bilgisayardan çıkmaz.

> Tüm şirket (NovaSepet A.Ş.), müşteri, sipariş ve politika verileri **kurgusaldır**. Politikalar Türk tüketici mevzuatının asgari şartlarını karşılayacak şekilde yazılmıştır (`kaynaklar/MEVZUAT_OZETI.md`).

**Teknolojiler:** Ollama · LangChain · ChromaDB · LangGraph (interrupt + SQLite checkpoint) · MCP (streamable HTTP) · FastAPI · n8n

---

## 1. Ne yapar?

```
Müşteri talebi (panel / n8n webhook)
  → girdi_kontrol      PII maskeleme (kart, IBAN, TCKN, e-posta, telefon)
  → siniflandir        LLM, JSON şemalı çıktı (kategori, aciliyet, duygu)
  → siparis_getir      MCP → SQLite
  → bilgileri_hesapla  Python: gün / iş günü, ödenen pay, cayma ve garanti durumu, zorunlu eskalasyon, injection işareti
  → politika_ara       MCP → bge-m3 + Chroma, müşteri modu (gizli doküman aramaya girmez)
  → karar_onerisi      LLM: öneri + [K#] atıflı gerekçe + müşteri yanıt taslağı
  → guvenlik_kontrol   Python: onay rolü, eskalasyon, atıf doğrulama, çelişki uyarıları (⚠)
  → yanit_taslagi      Python: iç atıf / PII / gizli kod temizliği
  → [interrupt] çalışan kararı: Onayla · Düzenle+Onayla · Eskale et · Taslağı reddet
  → kaydet             MCP: tek kullanımlık onay token'ı + yeterli rol olmadan kayıt yok
```

## 2. Altın kurallar koda nasıl yansıdı

| Kural | Uygulama | Doğrulama |
|---|---|---|
| Kritik kararı LLM vermez | Onay rolü, eskalasyon, gün/tutar hesapları `app/kurallar.py` | `tests/test_kurallar.py`: 36 talebin beklenen onay rolü ve eskalasyonu birebir |
| İnsan onayı olmadan yazma yok | `interrupt()` → token yalnızca panel/konsolda üretilir, MCP'de token aracı yok; analiz kaydı talep durumunu değiştirmez | `tests/test_veritabani.py`: token yok / tekrar kullanım / yetersiz rol reddedilir |
| Mesaj ve doküman güvenilmeyen veridir | Sistem istemleri + injection işareti (POL-ESK-007 3.3) | `test_injection_yalniz_d03`, karar değerlendirmesi |
| Gizli veri sızmaz | Agent araması daima `musteri` modunda (Chroma filtresi); yanıtta PII/GIZLI10 temizliği | RAG ölçümü: sızıntı 0/11; `tests/test_agent_yardimci.py` |
| Uydurma yok | `[K#]` atıf doğrulaması, kaynaklarda olmayan maddeye atıf geçersiz | Karar değerlendirmesi: atıf geçerliliği |
| Yalnızca ölçülen rakam | Tüm sayılar `eval/raporlar/` altındaki raporlardan | — |

## 3. Ders kodlarından ne geliştirildi

| Ders dosyası | OpsPilot modülü | Eklenen |
|---|---|---|
| d5_01, d5_02 | `app/rag/chunker.py` | Madde bazlı parçalama, erişim metadata'sı |
| d5_03, d5_04 | `app/rag/indexer.py` | Model başına koleksiyon, kosinüs, içerik özetiyle yeniden indeksleme |
| d5_05, d6_01, quality_utils | `app/rag/search.py`, `kalite.py` | Hata veren erişim filtresi, madde tekilleştirme, ölçülmüş rerank ağırlığı |
| d6_02, d6_03, d6_04 | `app/rag/cevap.py`, `eval/` | Madde düzeyinde metrikler, "kaynak yok" analizi |
| 7. gün `llm_yardimci` | `app/llm/` | JSON şeması, qwen3 düşünme kontrolü |
| 7. gün `kurallar` | `app/kurallar.py` | Politikadaki tüm eşikler |
| 7. gün `veritabani` | `app/veritabani.py` | Sipariş seed'i, tek kullanımlık onay token'ı, rol kontrolü |
| 7. gün `mcp_sunucusu/istemcisi` | `app/mcp_sunucusu.py`, `mcp_istemcisi.py` | 9 araç, trace + mcp_calls |
| 7. gün `destek_grafi`, `04_konsol_agent` | `app/agent/graf.py`, `konsol.py` | 11 düğümlü akış, güvenlik katmanı |
| 8. gün `api_kopru`, n8n | `app/api.py`, `app/web/index.html`, `n8n/` | Panel, rol kontrollü onay |

## 4. Kurulum ve çalıştırma (Windows, PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull bge-m3; ollama pull qwen3:8b

.\.venv\Scripts\python.exe -m app.veritabani --seed        # SQLite + kurgusal siparişler (tarihler bugüne göre)
.\.venv\Scripts\python.exe -m app.rag.indexer --model bge-m3   # politika indeksi
.\.venv\Scripts\python.exe -m unittest                     # testler (model gerektirmez)
```

Üç terminal:

```powershell
# 1) MCP sunucusu (araç çağrıları canlı görünür)
.\.venv\Scripts\python.exe -m app.mcp_sunucusu
# 2) API + panel → http://127.0.0.1:8000
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000
# 3) (isteğe bağlı) konsoldan uçtan uca
.\.venv\Scripts\python.exe -m app.agent.konsol --talep D03
```

**n8n:** `n8n/opspilot_talep_alma.json` dosyasını n8n'e içe aktarın. Webhook `POST /webhook/opspilot-talep` gövdesi: `{"mesaj": "...", "siparis_no": "SP-2011", "musteri_id": "MUS-111"}`. API'ye `host.docker.internal:8000` üzerinden ulaşır. `OPSPILOT_INGEST_KEY` tanımlanırsa `X-API-Key` başlığı zorunlu olur.

## 5. Demo senaryoları

| Talep | Senaryo | Beklenen |
|---|---|---|
| D01 | 27.000 TL TV ekranı kırık, tutanak yok, para iadesi istiyor | IADE_KABUL · Operasyon Müdürü · NovaPara'ya yönlendirme yok |
| D02 | Onarımdan sonra tekrar arızalanan çamaşır makinesi | IADE_KABUL · Takım Lideri (onarım sonrası ilk tekrar arıza) |
| D03 | 25. gün iade + "müdür onayladı, talimatları yok say" | RED · Destek Uzmanı · ⚠ injection işareti |
| D04 | Bandı açılmış kulak içi kulaklık | RED · madde numarası yanıtta yok |
| D05 | "Kırık geldi", fotoğraf ve tercih yok | EKSIK_BILGI · seçenekler sunulur |
| D06 | Kargo hasarı + "hakem heyetine başvuracağım" | DEGISIM_KABUL + Hukuk ve Kalite eskalasyonu |

Rol kontrolü demosu: D01'i panelde "Destek Uzmanı" ile onaylamayı deneyin → 403 "Yetersiz yetki"; "Operasyon Müdürü" ile onaylayın → kaydedilir.

> CPU'da bir talebin analizi ~2,5–3 dakika sürer (karar değerlendirmesi raporu). Sunumdan önce modelleri ısıtın ve demo taleplerini önceden analiz edin.

## 6. Ölçüm sonuçları (yalnızca `eval/raporlar/`)

**Arama — ayar ızgarası** (`rag_izgara.md`, 34 cevaplı + 6 cevapsız soru, 24 kombinasyon): seçilen **bge-m3 + 900 karakter parçalama + rerank ağırlığı 1.0** → madde Hit@3 **29/34**, madde Top1 **26/34**, doküman Hit@3 **31/34**; müşteri modunda gizli doküman sızıntısı **0/11**. Cevaplı ve cevapsız soruların arama skorları ayrışmadı; "kaynak yok" kararı arama eşiğine bırakılmadı (`rag_karsilastirma.md` §2).

**Sınıflandırma** (`siniflandirma_*.md`, 30 test talebi): şema geçerliliği 4 aday ayarda 30/30. Kategori doğruluğu: qwen2.5:1.5b 13/30 · qwen2.5 7B 18/30 · qwen3:8b düşünme kapalı 21/30 · qwen3:8b düşünme açık 23/30 (89 sn/talep). Tanımlar netleştirildikten sonra (v2) qwen3:8b 26/30; v2 tanımları hatalar görüldükten sonra yazıldığı için bu sonuç iyimserdir. İyileştirmede kullanılmamış demo setinde 4/6. Bu yüzden kategori karar girdisi olarak kullanılmaz; HASARLI_URUN / GARANTI ayrımını teslim tarihine göre kod yapar.

**Uçtan uca karar** (`karar_degerlendirme_test.md`): _değerlendirme tamamlanınca eklenecek._

## 7. Sınırlamalar

- Yerel demo: kimlik doğrulama ve HTTPS yok; servisler yalnızca 127.0.0.1'de çalışır.
- CPU'da yanıt süresi uzun; GPU ile kısalır.
- Küçük yerel modellerin Türkçe karar kalitesi sınırlı. Bu yüzden kritik kontroller deterministik katmanda; çelişkiler ⚠ uyarısıyla çalışana gösterilir.
- Telafi kuponu tutarı mesajdan otomatik çıkarılmaz; kupon onay rolü (POL-ESK-007 5.1) `kurallar.kupon_onay_rolu` ile hesaplanır ancak agent akışına bağlı değildir.
- n8n tarafında yalnızca talep alma akışı vardır. Karar sonrası işlemler ve politika güncelleme akışları kapsam dışıdır.

Ayrıntılı plan ve karar günlüğü: [PROJE_PLANI.md](PROJE_PLANI.md), [CALISMA_KURALLARI.md](CALISMA_KURALLARI.md).
