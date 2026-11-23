# Faz 3: Embedding Modelleri Karşılaştırma Raporu

**Tarih:** 23.11.2026 16:46
**Test seti:** `data/rag_sorular.json` — 40 soru (34 cevaplı, 6 cevapsız)
**Ayarlar:** 96 parça (madde bazlı, 900 karakter üstü bölünür), k=8, top_n=3, rerank=True, semantik ağırlık=0.7

**Yöntem notları**
- Hit/Top1 paydası yalnızca cevaplı sorulardır. Cevapsız sorular: 4 CEVAPSIZ + müşteri modunda cevabı yalnızca gizli dokümanda olan 2 GIZLI soru.
- Madde eşleşmesi ana madde düzeyindedir (beklenen 5.1 ise Madde 5 parçası isabettir). Aynı maddenin parçaları ilk 3'te tek kez sayılır.
- CAPRAZ sorularda beklenen dokümanların hepsi (madde için her dokümandan bir beklenen madde) ilk 3'te olmalıdır.
- Eşik analizi aynı soru setiyle yapıldığı için iyimserdir; eşik "en iyi sonucun benzerliği < eşik ise kaynak yok" kuralıdır.
- Arama süreleri model ısıtıldıktan sonra ölçülmüştür; sorgu embedding'i dahildir. Donanım: CPU.

## 1. Genel karşılaştırma

| Metrik | embeddinggemma | bge-m3 | qwen3-embedding:0.6b |
|---|---|---|---|
| Doküman Hit@3 | 32/34 (%94.1) | 31/34 (%91.2) | 32/34 (%94.1) |
| Madde Hit@3 | 27/34 (%79.4) | 27/34 (%79.4) | 25/34 (%73.5) |
| Top1 doküman | 27/34 (%79.4) | 27/34 (%79.4) | 27/34 (%79.4) |
| Top1 madde | 22/34 (%64.7) | 23/34 (%67.6) | 22/34 (%64.7) |
| Gizli doküman sızıntısı | 0/11 soru | 0/11 soru | 0/11 soru |
| Ortalama arama süresi | 52.5 ms | 132.3 ms | 241.4 ms |
| İndeksleme süresi | 36.69 sn | 77.66 sn | 156.03 sn |

## 2. "Kaynak yok" eşik analizi

| Metrik | embeddinggemma | bge-m3 | qwen3-embedding:0.6b |
|---|---|---|---|
| Cevaplı sorularda en düşük top1 benzerlik | 0.4359 | 0.515 | 0.3372 |
| Cevapsız sorularda en yüksek top1 benzerlik | 0.6322 | 0.6278 | 0.576 |
| İki grup tam ayrışıyor mu | hayır | hayır | hayır |
| En iyi eşik | 0.4906 | 0.4718 | 0.3196 |
| Yanlış alarm (cevaplı → 'kaynak yok') | 1/34 | 0/34 | 0/34 |
| Kaçan (cevapsız → kaynak var) | 3/6 | 5/6 | 5/6 |

## 3. Soru türüne göre madde Hit@3

| Soru türü | embeddinggemma | bge-m3 | qwen3-embedding:0.6b |
|---|---|---|---|
| DOGRUDAN | 9/9 (%100.0) | 9/9 (%100.0) | 9/9 (%100.0) |
| GUNLUK_DIL | 7/9 (%77.8) | 7/9 (%77.8) | 5/9 (%55.6) |
| ESKI_KURAL | 7/9 (%77.8) | 8/9 (%88.9) | 7/9 (%77.8) |
| CAPRAZ | 2/5 (%40.0) | 2/5 (%40.0) | 2/5 (%40.0) |
| GIZLI | 2/2 (%100.0) | 1/2 (%50.0) | 2/2 (%100.0) |

## 4. Madde isabeti olmayan sorular

**embeddinggemma:** R12 (GUNLUK_DIL), R17 (GUNLUK_DIL), R19 (ESKI_KURAL), R23 (ESKI_KURAL), R28 (CAPRAZ), R30 (CAPRAZ), R32 (CAPRAZ)

**bge-m3:** R11 (GUNLUK_DIL), R12 (GUNLUK_DIL), R23 (ESKI_KURAL), R28 (CAPRAZ), R30 (CAPRAZ), R32 (CAPRAZ), R40 (GIZLI)

**qwen3-embedding:0.6b:** R10 (GUNLUK_DIL), R11 (GUNLUK_DIL), R12 (GUNLUK_DIL), R14 (GUNLUK_DIL), R19 (ESKI_KURAL), R23 (ESKI_KURAL), R28 (CAPRAZ), R30 (CAPRAZ), R32 (CAPRAZ)

## 5. Yorum

Bu bölüm rakamlar birlikte incelendikten sonra yazılacaktır.
