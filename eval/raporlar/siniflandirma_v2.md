# Faz 3: Talep Sınıflandırma — Model Karşılaştırması

**Tarih:** 23.11.2026 18:56
**Test seti:** `data/ornek_talepler.json` T01–T30 (30 talep). Görev: yalnızca kategori (8 sınıf) + aciliyet/duygu/özet alanlarıyla şemalı JSON.
**Yöntem:** Ollama `/api/chat`, `format` = JSON şeması, temperature 0, seed 42. Her model ilk ölçümden önce ısıtıldı. Donanım: CPU.
Öneri (oneri) bu ölçümde yoktur; sipariş ve politika bilgisi gerektirdiği için Faz 5'te ölçülür.
**Kategori tanımları sürümü:** v2 (`app/llm/siniflandir.py`). v1 sonuçları: `siniflandirma_karsilastirma_v1.md`.

| Metrik | qwen3:8b (think=kapalı) |
|---|---|
| Şema geçerliliği | 30/30 (%100.0) |
| Kategori doğruluğu | 26/30 (%86.7) |
| Ortalama süre | 21.94 sn |
| En uzun süre | 29.22 sn |
| num_predict | 200 |
| Token sınırına takılan | 0/30 |
| Düşünme metni olan yanıt | 0/30 |
| Ort. düşünme metni (karakter) | 0 |

## Yanlış sınıflandırılan talepler

**qwen3:8b (think=kapalı):** T04 (IADE→HASARLI_URUN), T14 (IADE→PARA_IADESI), T22 (KAMPANYA→IADE), T29 (GARANTI→HASARLI_URUN)

## Yorum

Bu bölüm rakamlar birlikte incelendikten sonra yazılacaktır.
