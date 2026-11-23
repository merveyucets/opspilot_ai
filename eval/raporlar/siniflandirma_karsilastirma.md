# Faz 3: Talep Sınıflandırma — Model Karşılaştırması

**Tarih:** 23.11.2026 18:09
**Test seti:** `data/ornek_talepler.json` T01–T30 (30 talep). Görev: yalnızca kategori (8 sınıf) + aciliyet/duygu/özet alanlarıyla şemalı JSON.
**Yöntem:** Ollama `/api/chat`, `format` = JSON şeması, temperature 0, seed 42. Her model ilk ölçümden önce ısıtıldı. Donanım: CPU.
Öneri (oneri) bu ölçümde yoktur; sipariş ve politika bilgisi gerektirdiği için Faz 5'te ölçülür.

| Metrik | qwen2.5:1.5b | qwen2.5:latest | qwen3:8b (think=kapalı) | qwen3:8b (think=açık) |
|---|---|---|---|---|
| Şema geçerliliği | 30/30 (%100.0) | 30/30 (%100.0) | 30/30 (%100.0) | 30/30 (%100.0) |
| Kategori doğruluğu | 13/30 (%43.3) | 18/30 (%60.0) | 21/30 (%70.0) | 23/30 (%76.7) |
| Ortalama süre | 5.75 sn | 15.02 sn | 21.71 sn | 89.47 sn |
| En uzun süre | 7.67 sn | 24.23 sn | 28.74 sn | 136.77 sn |
| num_predict | 200 | 200 | 200 | 1536 |
| Token sınırına takılan | 0/30 | 0/30 | 0/30 | 0/30 |
| Düşünme metni olan yanıt | 0/30 | 0/30 | 0/30 | 30/30 |
| Ort. düşünme metni (karakter) | 0 | 0 | 0 | 1406 |

## Yanlış sınıflandırılan talepler

**qwen2.5:1.5b:** T01 (IADE→HASARLI_URUN), T02 (IADE→PARA_IADESI), T03 (IADE→DEGISIM), T04 (IADE→DEGISIM), T08 (GARANTI→HASARLI_URUN), T09 (KAMPANYA→HASARLI_URUN), T11 (IADE→DEGISIM), T12 (IADE→DEGISIM), T13 (IADE→HASARLI_URUN), T14 (IADE→DEGISIM), T15 (KAMPANYA→DEGISIM), T19 (KAMPANYA→KARGO), T20 (IADE→DEGISIM), T21 (KARGO→GENEL), T22 (KAMPANYA→GENEL), T29 (GARANTI→HASARLI_URUN), T30 (IADE→DEGISIM)

**qwen2.5:latest:** T02 (IADE→PARA_IADESI), T04 (IADE→DEGISIM), T06 (HASARLI_URUN→DEGISIM), T07 (HASARLI_URUN→IADE), T13 (IADE→DEGISIM), T14 (IADE→PARA_IADESI), T15 (KAMPANYA→PARA_IADESI), T19 (KAMPANYA→PARA_IADESI), T22 (KAMPANYA→IADE), T23 (HASARLI_URUN→DEGISIM), T28 (GENEL→PARA_IADESI), T29 (GARANTI→IADE)

**qwen3:8b (think=kapalı):** T02 (IADE→PARA_IADESI), T04 (IADE→DEGISIM), T06 (HASARLI_URUN→DEGISIM), T11 (IADE→DEGISIM), T13 (IADE→GENEL), T14 (IADE→PARA_IADESI), T22 (KAMPANYA→IADE), T23 (HASARLI_URUN→DEGISIM), T29 (GARANTI→HASARLI_URUN)

**qwen3:8b (think=açık):** T02 (IADE→PARA_IADESI), T04 (IADE→HASARLI_URUN), T07 (HASARLI_URUN→IADE), T14 (IADE→PARA_IADESI), T19 (KAMPANYA→PARA_IADESI), T22 (KAMPANYA→IADE), T29 (GARANTI→HASARLI_URUN)

## Yorum

Bu bölüm rakamlar birlikte incelendikten sonra yazılacaktır.
