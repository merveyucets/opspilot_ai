# Faz 3: Talep Sınıflandırma — Model Karşılaştırması

**Tarih:** 23.11.2026 18:59
**Set:** `data/ornek_talepler.json` — demo (6 talep). Görev: yalnızca kategori (8 sınıf) + aciliyet/duygu/özet alanlarıyla şemalı JSON.
**Yöntem:** Ollama `/api/chat`, `format` = JSON şeması, temperature 0, seed 42. Her model ilk ölçümden önce ısıtıldı. Donanım: CPU.
Öneri (oneri) bu ölçümde yoktur; sipariş ve politika bilgisi gerektirdiği için Faz 5'te ölçülür.
**Kategori tanımları sürümü:** v2 (`app/llm/siniflandir.py`). v1 sonuçları: `siniflandirma_karsilastirma_v1.md`.

| Metrik | qwen3:8b (think=kapalı) |
|---|---|
| Şema geçerliliği | 6/6 (%100.0) |
| Kategori doğruluğu | 4/6 (%66.7) |
| Ortalama süre | 24.3 sn |
| En uzun süre | 25.92 sn |
| num_predict | 200 |
| Token sınırına takılan | 0/6 |
| Düşünme metni olan yanıt | 0/6 |
| Ort. düşünme metni (karakter) | 0 |

## Yanlış sınıflandırılan talepler

**qwen3:8b (think=kapalı):** D02 (GARANTI→HASARLI_URUN), D04 (IADE→HASARLI_URUN)

## Yorum

Bu bölüm rakamlar birlikte incelendikten sonra yazılacaktır.
