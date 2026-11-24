"""Panel sunum mantığı (model gerektirmez; tests/test_panel.py).

- Analiz durumu: kuyrukta / çalışıyor / hazır / hata — agent'ın workflow_events kayıtlarından
- Müşteri görünümü: müşteri ekranına giden TEK veri biçimi. Yapay zekâ önerisi, gerekçe, uyarılar, onay rolü,
  taslak yanıt ASLA buraya girmez; müşteri yalnızca kendi mesajını, aşamayı ve ONAYLANMIŞ yanıtı görür
  (altın kural 2 ve 4: onaysız yanıt müşteriye gitmez, iç bilgi sızmaz).
"""
from __future__ import annotations

ANALIZ_ADIMLARI = [
    ("girdi_kontrol", "Girdi kontrolü"), ("siniflandir", "Sınıflandırma"), ("siparis_getir", "Sipariş"),
    ("bilgileri_hesapla", "Kurallar"), ("politika_ara", "Politika arama"), ("karar_onerisi", "Öneri"),
    ("guvenlik_kontrol", "Güvenlik"), ("yanit_taslagi", "Yanıt temizliği"), ("analiz_kaydet", "Kayıt"),
]
KARAR_DURUMLARI = {"KAPANDI", "ESKALE_EDILDI", "TASLAK_REDDEDILDI"}


def analiz_durumu(talep_no: str, analiz_var: bool, tamamlanan: set[str], kuyruk: list[str],
                  calisan: str | None, hatalar: dict[str, str]) -> dict:
    """Talebin analiz durumu. kuyruk: bekleyen + çalışan talepler (sırayla)."""
    adim = sum(1 for ad, _ in ANALIZ_ADIMLARI if ad in tamamlanan)
    if analiz_var and ("analiz_kaydet" in tamamlanan or talep_no not in kuyruk):
        return {"durum": "HAZIR", "adim": len(ANALIZ_ADIMLARI), "toplam": len(ANALIZ_ADIMLARI)}
    if talep_no == calisan:
        aktif = next((etiket for ad, etiket in ANALIZ_ADIMLARI if ad not in tamamlanan), None)
        return {"durum": "SURUYOR", "adim": adim, "toplam": len(ANALIZ_ADIMLARI), "aktif": aktif}
    if talep_no in kuyruk:
        return {"durum": "SIRADA", "adim": adim, "toplam": len(ANALIZ_ADIMLARI), "sira": kuyruk.index(talep_no)}
    if talep_no in hatalar:
        return {"durum": "HATA", "adim": adim, "toplam": len(ANALIZ_ADIMLARI), "hata": hatalar[talep_no]}
    # Analizi yok ve kuyrukta değil: sunucu yeniden başlamış ya da analiz yarıda kalmış olabilir
    return {"durum": "YOK", "adim": adim, "toplam": len(ANALIZ_ADIMLARI)}


def musteri_gorunumu(talep: dict) -> dict:
    """Müşteri ekranı için güvenli görünüm. `talep`: veritabani.musteri_talepleri() satırı."""
    k = talep.get("son_karar") or {}
    karar = k.get("karar")
    if karar in ("ONAYLA", "DUZENLE_ONAYLA"):
        asama, yanit = "YANITLANDI", k.get("gonderilen_yanit")
    elif karar == "ESKALE_ET":
        asama, yanit = "UZMANA_ILETILDI", None
    else:   # analiz sürüyor, karar bekliyor veya taslak reddedildi (yanıt henüz gönderilmedi)
        asama, yanit = ("INCELENIYOR" if talep.get("analiz_var") or karar == "REDDET" else "ALINDI"), None
    return {"talep_no": talep["talep_no"], "siparis_no": talep.get("siparis_no"), "tarih": talep["created_at"],
            "mesaj": talep["mesaj"], "asama": asama, "yanit": yanit,
            "yanit_tarihi": k.get("created_at") if yanit else None}
