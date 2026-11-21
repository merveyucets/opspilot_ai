# OpsPilot AI — Proje Planı

**Akıllı Müşteri Destek ve İade Süreci Asistanı**
BTK Akademi • Yapay Zekâ Çözümleri Kariyer Geliştirme Atölyesi • Hazırlayan: Merve YÜCETAŞ

> Tüm şirket, müşteri, sipariş ve politika verileri **kurgusaldır**. NovaSepet A.Ş. hayali bir e-ticaret şirketidir; politika kuralları Türk tüketici mevzuatı esas alınarak yazılmıştır.

---

## 1. Problem ve hedef

Destek uzmanı karmaşık bir iade/şikâyet talebi aldığında:
1. Talebin hangi prosedüre girdiğini bulmak için uzun politika dokümanlarını tarar,
2. Siparişin tarihini, tutarını, ürün tipini kontrol eder,
3. Kendi yetkisinin yetip yetmediğini çözmeye çalışır,
4. Müşteriye kurallara uygun bir yanıt yazar.

**OpsPilot AI** bu 4 adımı saniyeler içinde yapar, kaynak gösterir, ancak **son kararı her zaman çalışana bırakır** (human-in-the-loop). Tamamen yerel çalışır; müşteri verisi bilgisayardan dışarı çıkmaz.

## 2. Kesinleşen mimari kararlar

| # | Alan | Karar | Dayanak |
|---|---|---|---|
| 1 | Arayüz | FastAPI üzerinde tek sayfa web paneli (HTML + Tailwind CDN + Vanilla JS). Önce mockup → sade sürüm → görsel cila (SSE ile canlı agent adımları) | Derste FastAPI (Gün 8); panel projenin özgün katkısı |
| 2 | Karar mekanizması | **3 katman:** (1) Python araçları kesin bilgileri hesaplar → (2) LLM + RAG politika maddesine dayanarak öneri üretir → (3) deterministik güvenlik katmanı denetler | Hocanın `kurallar.py` ilkesi + hibrit RAG |
| 3 | İnsan onayı | LangGraph `interrupt()` + SQLite checkpoint + tek kullanımlık onay token'ı | `d7_06_agent.py`, `d7_store.py` |
| 4 | n8n | 3 workflow: talep alma, karar sonrası işlemler (Data Table giden kutusu/karar kaydı), politika güncelleme (`/ingest`) | `campus_ask/approve.json`, `embeding update/` |
| 5 | MCP | Streamable HTTP sunucu (:8001), her çağrı loglanır, `operation_key` ile idempotency | `mcp_sunucusu.py` |
| 6 | RAG | Madde bazlı bölümleme → `embeddinggemma` + Chroma → k=8 → hibrit rerank (anlamsal + lexical ağırlık deneyi) → top 3 → `[K1]` atıf + doğrulama | Gün 5-6, `benim_rag/rerank_karsilastirma.py` |
| 7 | Veri | 9 politika + 1 gizli iç doküman (sızıntı testi), 36 talep (12 onay / 12 red / 6 eksik bilgi / 6 eskalasyon; 30 test + 6 demo) | Hocanın kurgusal veri + `erisim` metadata yaklaşımı |
| 8 | Model | Faz 2'de ölçülerek seçilecek (hız + kalite) | GPU yok, CPU çıkarımı |
| 9 | Metrikler | Yalnızca ölçülen değerler raporlanır; "yalnız LLM" vs "LLM + güvenlik katmanı" karşılaştırılır | — |

### Güvenlik katmanının görevleri (karar 2)
- **Onay yetkisi** her zaman tutardan, koddan gelir (prompt injection ile değiştirilemez).
- **Zorunlu eskalasyonlar**: hukuki tehdit, son 30 günde 3+ şikâyet, KVKK talebi.
- **Şema ve atıf doğrulama**: JSON alanları geçerli mi, `[K#]` atıfları gerçek kaynaklara mı ait.
- **Çelişki uyarısı**: LLM önerisi kesin bilgilerle çelişirse sessizce düzeltmez, arayüzde "⚠ inceleyin" uyarısı gösterir.
- **Gizli veri filtresi**: `erisim: gizli` dokümanlar müşteri yanıtı üretiminde kullanılmaz.

## 3. Mimari

```
 Müşteri talebi (n8n Form / Webhook)          Destek Uzmanı Paneli (tarayıcı)
            │                                          │  ▲  SSE: canlı agent adımları
            ▼                                          ▼  │
   ┌─────────────────┐  host.docker.internal  ┌──────────────────────────┐
   │  n8n (Docker)   │ ─────────────────────► │  FastAPI :8000           │
   │  :5678          │ ◄───── karar olayı ─── │  /analyze /approve       │
   │  Data Table     │                        │  /ingest /tickets /audit │
   └─────────────────┘                        └────────────┬─────────────┘
                                                           ▼
                                              ┌──────────────────────────┐
                                              │ LangGraph Agent          │ checkpoint: SQLite
                                              │ interrupt() = HITL       │
                                              └────────────┬─────────────┘
                                                           │ MCP (streamable HTTP :8001)
                                                           ▼
                                              ┌──────────────────────────┐
                                              │ MCP Server               │
                                              │  politika_ara ───────────┼──► Chroma + embeddinggemma
                                              │  siparis_getir ──────────┼──► SQLite (sipariş, talep,
                                              │  talep_kaydet / karar... │      karar, audit)
                                              └──────────────────────────┘
                        Ollama :11434 — tüm modeller yerel
```

## 4. Agent akışı (LangGraph)

```
START
  → girdi_kontrol     (boş/uzun mesaj, PII maskeleme, injection işaretleri)
  → siniflandir       (LLM JSON + kural yedeği: kategori, aciliyet, duygu)
  → siparis_getir     (MCP; sipariş no yoksa → EKSIK_BILGI kolu)
  → bilgileri_hesapla (Python: gün/iş günü, tutar, ürün bayrakları, şikâyet sayısı)
  → politika_ara      (MCP → RAG: k=8 → rerank → top 3)
  → karar_onerisi     (LLM: bilgiler + maddeler → öneri JSON + gerekçe [K#])
  → guvenlik_kontrol  (yetki seviyesi, zorunlu eskalasyon, şema/atıf, çelişki uyarısı)
  → yanit_taslagi     (LLM: duygu durumuna uygun müşteri yanıtı, POL-ILT-008 kuralları)
  → [interrupt] calisan_karari   ← panel / n8n buradan devam ettirir
        ├─ ONAYLA            → onay token'ı → MCP karar_kaydet → n8n giden kutusu
        ├─ DÜZENLE + ONAYLA  → aynı + AI taslağı ile düzenleme farkı kaydı
        ├─ ESKALE ET         → yetki matrisine göre ilgili ekip kuyruğu
        └─ REDDET (taslağı)  → kayıt, yanıt gönderilmez
  → END
```

## 5. Fazlar

Her faz aynı döngüyle ilerler: **yaz → birlikte test et → Merve kendi bilgisayarında çalıştırıp anlar → commit**. Bir faz onaylanmadan sonrakine geçilmez.

| Faz | İçerik | Kabul kriteri |
|---|---|---|
| 0 | Repo, sanal ortam, config, plan | ✅ Temiz kurulum, importlar çalışıyor |
| 1 | Bilgi bankası: 9 politika (madde numaralı, mevzuat dayanaklı) + 1 gizli doküman + metadata | Her doküman onaylandı |
| 2 | Talep veri seti (36) + sipariş/müşteri verisi + RAG soru seti | 12/12/6/6 dağılımı, her talebin beklenen cevabı politikada var |
| 3 | RAG hattı + değerlendirme + model/embedding ölçümü | Hit@3 ve atıf geçerliliği raporu, model seçimi |
| 4 | Araçlar, kurallar, güvenlik katmanı, SQLite, MCP Server/Client | Birim testleri yeşil, araçlar MCP üzerinden çağrılıyor |
| 5 | LangGraph agent + interrupt + checkpoint | Konsoldan uçtan uca: onay / düzenle / eskale / red |
| 6 | FastAPI (+ SSE) | Swagger'dan tam döngü |
| 7 | Web paneli: mockup → sade sürüm → cila | Demo senaryoları panelden sorunsuz |
| 8 | n8n workflow'ları + docker-compose | 3 akış uçtan uca çalışıyor |
| 9 | Değerlendirme raporu, güvenlik testleri, README, sunum + yedek video | Teslime hazır repo |

## 6. Değerlendirme planı

- **RAG**: soru seti → beklenen doküman/madde; Hit@3, rerank Top1, atıf geçerlilik oranı; embedding modeli karşılaştırması.
- **Karar**: 30 test talebi → kategori, öneri, onay seviyesi doğruluğu; "yalnız LLM" vs "LLM + güvenlik katmanı"; hatalı onay oranı.
- **Güvenlik**: prompt injection, gizli doküman sızıntısı, PII, onaysız yazma girişimi.
- **Performans**: talep başına analiz süresi (CPU).

## 7. Kapsam dışı / sınırlamalar

- Gerçek kimlik doğrulama, HTTPS ve rol yönetimi yok (yerel demo). İnternete açılmaz.
- Gerçek e-posta gönderilmez; n8n Data Table "giden kutusu" olarak kullanılır (Gmail isteğe bağlı).
- Yerel küçük modellerin Türkçe kalitesi sınırlıdır; bu nedenle kritik kontroller deterministik katmandadır.
