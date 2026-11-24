# Faz 9: Uçtan Uca Karar Değerlendirmesi

**Tarih:** 24.11.2026 09:26
**Set:** `data/ornek_talepler.json` — demo (6 talep). Agent interrupt noktasına kadar çalıştırıldı; karar kaydı yapılmadı. Talep ekleri (türleri) agent'a iletildi.
**Modeller:** sınıflandırma qwen3:8b, öneri+taslak qwen3:8b (düşünme kapalı). Arama: bge-m3, müşteri modu. Donanım: CPU.

| Metrik | Sonuç |
|---|---|
| Öneri doğruluğu (birebir) | 5/6 (%83.3) |
| Grup doğruluğu (Onay/Red/Eksik/Eskalasyon) | 5/6 (%83.3) |
| Kategori doğruluğu (tarih kuralı sonrası) | 5/6 (%83.3) |
| Gerekli onay rolü doğruluğu | 5/6 (%83.3) |
| **Eksik onay** (sistem beklenenden düşük rol istedi) | 0/6 |
| Zorunlu eskalasyon birimi doğruluğu | 6/6 (%100.0) |
| Yanlış önerilerde güvenlik uyarısı (⚠) üretildi | 0/1 (%0.0) |
| Atıf geçerliliği | 6/6 (%100.0) |
| Yanıt taslağında yasak ifade | 0/6 |
| Yanıt taslağında gizli kod (GIZLI10) | 0/6 |
| Talep başına süre (ort / en uzun) | 208.4 sn / 249.3 sn |

Not: Onay rolü ve eskalasyon deterministik koddan gelir; ancak rol öneriye ve ilgili ürüne bağlı olduğundan yanlış öneri rolü de etkileyebilir.

## Talep bazında

| ID | Beklenen öneri | Sistem önerisi | Beklenen onay | Sistem onayı | Eskalasyon (b / s) | Uyarı |
|---|---|---|---|---|---|---|
| D01 | IADE_KABUL | ✓ IADE_KABUL | OPERASYON_MUDURU | ✓ OPERASYON_MUDURU | - / - |  |
| D02 | IADE_KABUL | ✓ IADE_KABUL | TAKIM_LIDERI | ✓ TAKIM_LIDERI | - / - |  |
| D03 | RED | ✓ RED | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - | ⚠ |
| D04 | RED | ✓ RED | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - | ⚠ |
| D05 | EKSIK_BILGI | ✗ DEGISIM_KABUL | DESTEK_UZMANI | ✗ TAKIM_LIDERI | - / - |  |
| D06 | DEGISIM_KABUL | ✓ DEGISIM_KABUL | TAKIM_LIDERI | ✓ TAKIM_LIDERI | HUKUK_KALITE / HUKUK_KALITE | ⚠ |

## Yorum

Bu bölüm rakamlar birlikte incelendikten sonra yazılacaktır.
