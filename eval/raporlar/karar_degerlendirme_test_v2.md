# Faz 9: Uçtan Uca Karar Değerlendirmesi

**Tarih:** 24.11.2026 09:29
**Set:** `data/ornek_talepler.json` — test (30 talep). Agent interrupt noktasına kadar çalıştırıldı; karar kaydı yapılmadı. Talep ekleri (türleri) agent'a iletildi.
**Modeller:** sınıflandırma qwen3:8b, öneri+taslak qwen3:8b (düşünme kapalı). Arama: bge-m3, müşteri modu. Donanım: CPU.

| Metrik | Sonuç |
|---|---|
| Öneri doğruluğu (birebir) | 12/30 (%40.0) |
| Grup doğruluğu (Onay/Red/Eksik/Eskalasyon) | 15/30 (%50.0) |
| Kategori doğruluğu (tarih kuralı sonrası) | 27/30 (%90.0) |
| Gerekli onay rolü doğruluğu | 29/30 (%96.7) |
| **Eksik onay** (sistem beklenenden düşük rol istedi) | 0/30 |
| Zorunlu eskalasyon birimi doğruluğu | 30/30 (%100.0) |
| Yanlış önerilerde güvenlik uyarısı (⚠) üretildi | 4/18 (%22.2) |
| Atıf geçerliliği | 29/30 (%96.7) |
| Yanıt taslağında yasak ifade | 0/30 |
| Yanıt taslağında gizli kod (GIZLI10) | 0/30 |
| Talep başına süre (ort / en uzun) | 196.3 sn / 314.8 sn |

Not: Onay rolü ve eskalasyon deterministik koddan gelir; ancak rol öneriye ve ilgili ürüne bağlı olduğundan yanlış öneri rolü de etkileyebilir.

## Talep bazında

| ID | Beklenen öneri | Sistem önerisi | Beklenen onay | Sistem onayı | Eskalasyon (b / s) | Uyarı |
|---|---|---|---|---|---|---|
| T01 | IADE_KABUL | ✓ IADE_KABUL | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T02 | IADE_KABUL | ✓ IADE_KABUL | OPERASYON_MUDURU | ✓ OPERASYON_MUDURU | - / - |  |
| T03 | IADE_KABUL | ✓ IADE_KABUL | TAKIM_LIDERI | ✓ TAKIM_LIDERI | - / - |  |
| T04 | IADE_KABUL | ✗ DEGISIM_KABUL | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T05 | DEGISIM_KABUL | ✗ EKSIK_BILGI | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T06 | DEGISIM_KABUL | ✓ DEGISIM_KABUL | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T07 | IADE_KABUL | ✓ IADE_KABUL | TAKIM_LIDERI | ✓ TAKIM_LIDERI | - / - |  |
| T08 | SERVISE_YONLENDIR | ✗ EKSIK_BILGI | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T09 | IADE_KABUL | ✓ IADE_KABUL | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T10 | KARGO_SORUSTURMA | ✓ KARGO_SORUSTURMA | TAKIM_LIDERI | ✓ TAKIM_LIDERI | - / - |  |
| T11 | RED | ✗ EKSIK_BILGI | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T12 | RED | ✗ EKSIK_BILGI | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T13 | RED | ✗ IADE_KABUL | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - | ⚠ |
| T14 | RED | ✗ IADE_KABUL | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T15 | RED | ✓ RED | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T16 | RED | ✗ EKSIK_BILGI | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T17 | RED | ✗ EKSIK_BILGI | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T18 | RED | ✗ SERVISE_YONLENDIR | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T19 | RED | ✗ ESKALASYON | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T20 | RED | ✗ IADE_KABUL | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - | ⚠ |
| T21 | EKSIK_BILGI | ✓ EKSIK_BILGI | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T22 | EKSIK_BILGI | ✗ IADE_KABUL | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T23 | EKSIK_BILGI | ✗ IADE_KABUL | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T24 | EKSIK_BILGI | ✗ DEGISIM_KABUL | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T25 | EKSIK_BILGI | ✗ IADE_KABUL | DESTEK_UZMANI | ✓ DESTEK_UZMANI | - / - |  |
| T26 | ESKALASYON | ✓ ESKALASYON | DESTEK_UZMANI | ✓ DESTEK_UZMANI | KVKK / KVKK |  |
| T27 | KARGO_SORUSTURMA | ✓ KARGO_SORUSTURMA | DESTEK_UZMANI | ✗ TAKIM_LIDERI | KALITE_KONTROL / KALITE_KONTROL | ⚠ |
| T28 | ESKALASYON | ✗ EKSIK_BILGI | DESTEK_UZMANI | ✓ DESTEK_UZMANI | GUVENLIK / GUVENLIK | ⚠ |
| T29 | IADE_KABUL | ✗ RED | DESTEK_UZMANI | ✓ DESTEK_UZMANI | URUN_GUVENLIGI / URUN_GUVENLIGI | ⚠ |
| T30 | ESKALASYON | ✓ ESKALASYON | TAKIM_LIDERI | ✓ TAKIM_LIDERI | POLITIKA_ISTISNASI / POLITIKA_ISTISNASI |  |

## Yorum

Bu bölüm rakamlar birlikte incelendikten sonra yazılacaktır.
