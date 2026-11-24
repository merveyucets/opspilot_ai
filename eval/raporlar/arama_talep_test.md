# Faz 9: Talep mesajlarıyla politika araması — tek sorgu vs çoklu sorgu

**Tarih:** 24.11.2026 00:59
**Set:** `data/ornek_talepler.json` — test (30 talep; beklenen maddesi olan 30). Arama: bge-m3, müşteri modu.
**Arama soruları:** sınıflandırıcı (qwen3:8b, düşünme kapalı) aynı çağrıda 2-3 soru yazar; mesaj + sorular RRF ile birleştirilir.
**Beklenen maddeler:** `beklenen.dayanak` (ana madde). POL-ESK-007 Madde 2 hariç (onay yetkisini kod hesaplar).
**Seçim kuralı (ölçümden önce):** "hepsi bulundu" en yüksek → eşitlikte madde duyarlılığı → eşitlikte küçük N.

| Varyant | Beklenen maddelerin hepsi bulundu | En az biri bulundu | Madde duyarlılığı | Gizli doküman | Arama süresi (ort.) |
|---|---|---|---|---|---|
| mesaj_top3 | 7/30 (%23.3) | 19/30 (%63.3) | 21/58 (%36.2) | 0 | 0.22 sn |
| **mesaj_top5** (seçilen) | 10/30 (%33.3) | 23/30 (%76.7) | 27/58 (%46.6) | 0 | 0.22 sn |
| rrf_top3 | 5/30 (%16.7) | 16/30 (%53.3) | 18/58 (%31.0) | 0 | 0.54 sn |
| rrf_top5 | 9/30 (%30.0) | 21/30 (%70.0) | 26/58 (%44.8) | 0 | 0.53 sn |
| donusumlu_top3 | 6/30 (%20.0) | 17/30 (%56.7) | 19/58 (%32.8) | 0 | 0.54 sn |
| donusumlu_top5 | 9/30 (%30.0) | 23/30 (%76.7) | 26/58 (%44.8) | 0 | 0.54 sn |

**Sınıflandırıcı (arama soruları eklendikten sonra):** kategori doğruluğu 25/30 (%83.3) (ham LLM, tarih kuralı öncesi) ·
şema hatası 0/30 · süre ort. 224.1 sn / en uzun 5621.05 sn.
Karşılaştırma: arama soruları eklenmeden önce v2 tanımlarıyla test setinde 26/30 (`siniflandirma_v2.md`).

## Talep bazında

| ID | Beklenen | mesaj_top3 | rrf_top3 | donusumlu_top3 | donusumlu_top5 | Arama soruları |
|---|---|---|---|---|---|---|
| T01 | POL-IADE-001 Md.3, POL-IADE-001 Md.5, POL-IADE-001 Md.7, POL-PARA-002 Md.3 | 1/4 | 1/4 | 1/4 | 1/4 | El blender seti iade edilebilir mi? · Kutuya geri konulan ürün için iade süreci nasıl çalışır? · Ürünün tesliminden 7 gün içinde arızası olmamışsa iade süreci ne şekilde yürütülür? |
| T02 | POL-IADE-001 Md.3, POL-PARA-002 Md.3 | 1/2 | 1/2 | 1/2 | 1/2 | Dizüstü bilgisayar iade edilebilir mi? · Dizüstü bilgisayar için değişim yapılır mı? · İade süreci tamamlandıktan sonra taksit taksit para iadesi yapılır mı? |
| T03 | POL-IADE-001 Md.2, POL-IADE-001 Md.3 | 0/2 | 0/2 | 0/2 | 0/2 | Robot süpürge için iade süresi ne kadardır? · Kusursuz ürün iade edilebilir mi? · İade süreci başlatılmışsa para ne zaman iade edilir? |
| T04 | POL-IADE-001 Md.3, POL-IADE-001 Md.6 | 1/2 | 0/2 | 1/2 | 1/2 | Yanlış modelde ürün gönderildiğinde iade edilebilir mi? · Mühürlü ambalaj açılmadan iade işlemini gerçekleştirmek mümkün mü? · Yanlış model ürün için ne tür belgeler gereklidir? |
| T05 | POL-DEG-005 Md.2, POL-DEG-005 Md.3, POL-DEG-005 Md.5 | 2/3 | 2/3 | 2/3 | 2/3 | Kapüşonlu mont için değişim yapılır mı? · Beden değişim isteğinde hangi bilgi veya belge gerekir? |
| T06 | POL-DEG-005 Md.1, POL-HSR-004 Md.5 | 1/2 | 1/2 | 1/2 | 1/2 | Kargo sırasında ürünün yanlış renk ve beden gönderildi mi? · Yanlış ürün gönderildiğinde ne yapılır? · Kargo sırasında ürünün hasarlı olup olmadığı kontrol edilir mi? |
| T07 | POL-HSR-004 Md.4, POL-KMP-009 Md.6, POL-KMP-009 Md.8, POL-PARA-002 Md.2 | 0/4 | 0/4 | 0/4 | 0/4 | Filtre kahve makinesi iade edilebilir mi? · Kargoda hasarlı ürün için ne yapılır? · İade edilen ürünün para iadesi nasıl yapılır? |
| T08 | POL-GAR-003 Md.3, POL-GAR-003 Md.6 | 1/2 | 1/2 | 1/2 | 1/2 | Telefon arızası garanti süresi içinde mi? · Telefonun arızası kusur sayılır mı? · Arıza nedeniyle garanti kapsamında onarım yapılır mı? |
| T09 | POL-KMP-009 Md.2, POL-KMP-009 Md.4 | 2/2 | 1/2 | 1/2 | 2/2 | 3 Al 2 Öde kampanyasında ürün iade edildiğinde diğer ürünler için ek ücret alınır mı? · Kampanya kapsamında alınan ürünlerden birinin iade edilmesi durumunda ne yapılır? · Kampanya süresi sona erdikten sonra ürün iade edilmesi durumunda ne yapılır? |
| T10 | POL-ESK-007 Md.5, POL-KRG-006 Md.4 | 1/2 | 1/2 | 1/2 | 1/2 | Kargoda kalmış ürün için gecikme süresi ne kadardır? · Kargoda kalmış ürünler için indirim kuponu tanımlanabilir mi? · Kargoda kalmış ürünün teslimat süresi ne kadardır? |
| T11 | POL-ESK-007 Md.4, POL-IADE-001 Md.3 | 0/2 | 0/2 | 0/2 | 0/2 | Koşu ayakkabısı iade edilebilir mi? · İade süreci için hangi bilgi veya belge gerekir? |
| T12 | POL-IADE-001 Md.6 | 0/1 | 0/1 | 0/1 | 0/1 | Çekirdek kahve iade edilebilir mi? · Kahve tadını beğenmedikten sonra iade süreci nasıl çalışır? · İade edilen ürünün miktarı ne kadar olursa iade işlemini tamamlar mı? |
| T13 | POL-DEG-005 Md.3, POL-IADE-001 Md.6 | 1/2 | 0/2 | 0/2 | 1/2 | Kıyafet için değişim yapılır mı? · Renk tercihindeki farklılık durumunda ne yapılır? |
| T14 | POL-IADE-001 Md.6 | 1/1 | 1/1 | 1/1 | 1/1 | Dijital hediye kartı için para iadesi süreci başlatıldı mı? · Dijital hediye kartı iade edildiğinde para ne şekilde geri çevrilir? · Dijital hediye kartı iade talebi için hangi bilgi veya belge gerekir? |
| T15 | POL-KMP-009 Md.9 | 1/1 | 0/1 | 0/1 | 1/1 | Kampanyalı siparişte kısmi iade tutarı nasıl hesaplanır? · Fiyat farkı durumunda ne yapılır? · Kahve öğütücüsü için kampanya kapsamında iade yapılabilir mi? |
| T16 | POL-DEG-005 Md.2 | 1/1 | 1/1 | 1/1 | 1/1 | Gömlek için değişim yapılır mı? · Beden değiştirme işleminde hangi bilgi veya belge gerekir? |
| T17 | POL-DEG-005 Md.2, POL-IADE-001 Md.3 | 0/2 | 1/2 | 0/2 | 0/2 | Kulaklık için değişim yapılır mı? · Renk değişikliği durumunda ne yapılır? |
| T18 | POL-GAR-003 Md.2, POL-GAR-003 Md.7, POL-ILT-008 Md.8 | 1/3 | 0/3 | 0/3 | 1/3 | Blender ürününde teslimden 7 günden sonra arıza tespit edildi mi? · Blender ürününün garanti süresi içinde ücretsiz tamir edilmesi için hangi belgeler gereklidir? · Blender ürününde arıza durumunda ne tür bir işlem yapılır? |
| T19 | POL-ESK-007 Md.5 | 1/1 | 0/1 | 1/1 | 1/1 | Kampanyalı siparişte kısmi iade tutarı nasıl hesaplanır? · Sipariş gecikmesi nedeniyle verilen kuponun nakit olarak iade edilmesi mümkün müdür? · Kampanyalı siparişte kuponun nakit olarak iade edilmesi süreci nedir? |
| T20 | POL-IADE-001 Md.6 | 1/1 | 1/1 | 1/1 | 1/1 | Konsol oyunu iade edilebilir mi? · İade süreci için hangi bilgi veya belge gerekir? · İade edilen ürünün ambalajı açılmışsa ne yapılır? |
| T21 | POL-KRG-006 Md.8 | 0/1 | 0/1 | 0/1 | 1/1 | Kargonun teslimat süresi ne kadardır? · Kargonun gecikme süresi ne kadardır? · Kargonun takip numarası ve durumu nedir? |
| T22 | POL-KMP-009 Md.10, POL-KMP-009 Md.2 | 0/2 | 0/2 | 0/2 | 1/2 | Ürün iade edilebilir mi? · İade süreci için hangi bilgi veya belge gerekir? · İade tutarı ne kadar olur? |
| T23 | POL-HSR-004 Md.4 | 0/1 | 0/1 | 0/1 | 0/1 | Bluetooth hoparlör iade edilebilir mi? · Kargoda hasarlı ürün için ne yapılır? · Şarj olmayan ürün için değişim yapılır mı? |
| T24 | POL-DEG-005 Md.1, POL-DEG-005 Md.6 | 1/2 | 1/2 | 1/2 | 1/2 | Elbise için değişim yapılır mı? · Değişim işleminde hangi bilgi veya belge gerekir? |
| T25 | POL-ILT-008 Md.6, POL-PARA-002 Md.3 | 1/2 | 1/2 | 1/2 | 1/2 | Kapıda nakit ödeme durumunda para iadesi nasıl yapılır? · Nakit ödemelerde iade tutarı ne şekilde hesaplanır? · Para iadesi için gerekli olan hesap bilgileri nelerdir? |
| T26 | POL-ESK-007 Md.6 | 1/1 | 1/1 | 1/1 | 1/1 | Kişisel veri silme talepleri nasıl işlenir? · Müşteri verilerinin silinmesi süreci ne şekilde yürütülür? |
| T27 | POL-ESK-007 Md.6, POL-KRG-006 Md.4 | 1/2 | 1/2 | 0/2 | 1/2 | Şarjlı süpürgenin kargoda kalma süresi ne kadardır? · Kargoda kalmış ürünün takip bilgisi nasıl sağlanır? · Kargoda kalmış ürünün teslimat süresi ne kadardır? |
| T28 | POL-ESK-007 Md.6, POL-ILT-008 Md.6 | 0/2 | 2/2 | 2/2 | 2/2 | Kişisel hesap güvenliği ile ilgili kullanıcı hesabında bilinmeden yapılan işlem durumunda ne yapılır? · Kullanıcının hesabına bilinmeden yapılan siparişler için hangi bilgi veya belge gerekir? · Hesap güvenliği ihlalleri durumunda kullanıcıya ne tür destek sağlanır? |
| T29 | POL-ESK-007 Md.6, POL-ESK-007 Md.7, POL-GAR-003 Md.4 | 0/3 | 0/3 | 1/3 | 1/3 | Saç kurutma makinesi iade edilebilir mi? · Makine kullanırken duman ve yanık kokusu geldi durumunda ne yapılır? · Kullanım sırasında arıza yaşanan ürün için hangi bilgi veya belge gerekir? |
| T30 | POL-ESK-007 Md.4, POL-IADE-001 Md.3 | 0/2 | 0/2 | 0/2 | 0/2 | Hava temizleyici iade edilebilir mi? · Kullanılmadığı belgelenmiş ürün için iade süresi geçtiğinde ne yapılır? · İade süreci için hangi belgeler gerekir? |

## Yorum

Bu bölüm rakamlar birlikte incelendikten sonra yazılacaktır.
