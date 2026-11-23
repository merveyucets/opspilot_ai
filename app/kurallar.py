"""Deterministik iş kuralları (altın kural 1: kritik kararı LLM vermez).

Ders kodu `7. Gün Kodlar Tekrar/kurallar.py`'den (anahtar kelimeyle kural, öncelik belirleme) geliştirildi.
Her fonksiyon dayandığı politika maddesini docstring'de belirtir. Model gerektirmez; tests/test_kurallar.py.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

# --- Eşikler (politikalardaki rakamlar) ---
CAYMA_GUN = 14                    # POL-IADE-001 3.1
GRI_ALAN_GUN = 2                  # POL-ESK-007 4.4: süreyi en fazla 2 gün aşan
GRI_ALAN_TUTAR = 2500.0           # POL-ESK-007 4.4
KUTUDAN_ARIZALI_GUN = 7           # POL-HSR-004 4.1, POL-GAR-003 1.2
DEGISIM_GUN = 30                  # POL-DEG-005 2.1
GECIKME_IS_GUNU = 7               # POL-KRG-006 4.1
KAYIP_IS_GUNU = 15                # POL-KRG-006 5.1
SIKAYET_ESIGI = 3                 # POL-ESK-007 6.2 (mevcut talep dahil)
ONAY_ESIKLERI = [(2500.0, "DESTEK_UZMANI"), (15000.0, "TAKIM_LIDERI")]   # POL-ESK-007 2.1
KUPON_ESIKLERI = [(150.0, "DESTEK_UZMANI"), (1000.0, "TAKIM_LIDERI")]    # POL-ESK-007 5.1
ROL_SIRASI = ["DESTEK_UZMANI", "TAKIM_LIDERI", "OPERASYON_MUDURU"]

# Resmî tatiller (POL-GAR-003 3.7 / POL-KRG-006 1.3 — pazar ve bu günler iş günü değildir; cumartesi iş günüdür).
# Sabit tarihli tatiller + 2026-2027 dinî bayramlar (kurgusal demo için yaklaşık liste).
SABIT_TATILLER = {(1, 1), (4, 23), (5, 1), (5, 19), (7, 15), (8, 30), (10, 29)}
DINI_BAYRAMLAR = {
    date(2026, 3, 20), date(2026, 3, 21), date(2026, 3, 22),
    date(2026, 5, 27), date(2026, 5, 28), date(2026, 5, 29), date(2026, 5, 30),
    date(2027, 3, 9), date(2027, 3, 10), date(2027, 3, 11),
    date(2027, 5, 16), date(2027, 5, 17), date(2027, 5, 18), date(2027, 5, 19),
}


def normalize(metin: str) -> str:
    """Küçük harf + Türkçe karakter sadeleştirme (ders: kurallar.normalize)."""
    metin = metin.replace("İ", "i").replace("I", "ı").lower()
    tablo = str.maketrans("çğıöşü", "cgiosu")
    metin = unicodedata.normalize("NFKC", metin).translate(tablo)
    return re.sub(r"\s+", " ", metin)


# --- Tarih hesapları ---
def is_gunu_mu(g: date) -> bool:
    return g.weekday() != 6 and (g.month, g.day) not in SABIT_TATILLER and g not in DINI_BAYRAMLAR


def is_gunu_say(baslangic: date, bitis: date) -> int:
    """baslangic'tan sonraki günden bitis dahil, iş günü sayısı."""
    return sum(1 for i in range(1, (bitis - baslangic).days + 1) if is_gunu_mu(baslangic + timedelta(days=i)))


def cayma_durumu(gecen_gun: int) -> str:
    """POL-IADE-001 3.1 / POL-ESK-007 4.4: SURE_ICI (≤14), GRI (15-16), SURE_DISI (≥17)."""
    if gecen_gun <= CAYMA_GUN:
        return "SURE_ICI"
    if gecen_gun <= CAYMA_GUN + GRI_ALAN_GUN:
        return "GRI"
    return "SURE_DISI"


def kusur_kategorisi(gecen_gun: int) -> str:
    """Kusurlu/arızalı üründe politika: ilk 7 gün POL-HSR-004, sonrası POL-GAR-003."""
    return "HASARLI_URUN" if gecen_gun <= KUTUDAN_ARIZALI_GUN else "GARANTI"


def kargo_durumu(kargo_is_gunu: int) -> str:
    """POL-KRG-006 4.1 / 5.1."""
    if kargo_is_gunu >= KAYIP_IS_GUNU:
        return "KAYIP"
    if kargo_is_gunu > GECIKME_IS_GUNU:
        return "GECIKMIS"
    return "NORMAL"


# --- Tutar hesapları ---
def odenen_paylar(kalemler: list[dict], indirim: float) -> dict[int, float]:
    """POL-KMP-009 3.1/3.3/4.1: indirim liste fiyatı oranında dağıtılır; kuruş farkı son ürüne.
    Hediye ürünler (liste fiyatı 0) dağıtıma girmez."""
    ucretli = [k for k in kalemler if not k.get("hediye")]
    toplam = sum(k["liste_fiyati"] for k in ucretli)
    paylar = {}
    for k in ucretli:
        paylar[k["kalem_no"]] = round(k["liste_fiyati"] - indirim * k["liste_fiyati"] / toplam, 2) if toplam else 0.0
    if ucretli:
        son = ucretli[-1]["kalem_no"]
        paylar[son] = round(toplam - indirim - sum(v for n, v in paylar.items() if n != son), 2)
    return paylar


def onay_rolu(tutar: float | None) -> str:
    """POL-ESK-007 2.1: ≤2.500 DU, ≤15.000 TL, üzeri OM."""
    if tutar is None:
        return "DESTEK_UZMANI"
    for esik, rol in ONAY_ESIKLERI:
        if tutar <= esik:
            return rol
    return "OPERASYON_MUDURU"


def kupon_onay_rolu(tutar: float) -> str:
    """POL-ESK-007 5.1: ≤150 DU, ≤1.000 TL, üzeri OM."""
    for esik, rol in KUPON_ESIKLERI:
        if tutar <= esik:
            return rol
    return "OPERASYON_MUDURU"


def en_ust_rol(*roller: str) -> str:
    """POL-ESK-007 7.1: birden fazla kural varsa en üst onay seviyesi."""
    return max(roller, key=ROL_SIRASI.index)


def gerekli_onay(oneri: str, islem_tutari: float | None, politika_istisnasi: bool = False,
                 kupon_tutari: float | None = None) -> str:
    """Önerinin gerektirdiği onay rolü.
    - RED / EKSIK_BILGI: tutardan bağımsız DU (POL-ESK-007 2.4)
    - Politika istisnası: en az TL, 15.000 üzeri OM (4.2)
    - Kupon: 5.1; birden fazla kural: en üst seviye (7.1)
    """
    if oneri in ("RED", "EKSIK_BILGI"):
        rol = "DESTEK_UZMANI"
    else:
        rol = onay_rolu(islem_tutari)
    if politika_istisnasi:
        rol = en_ust_rol(rol, "TAKIM_LIDERI")
    if kupon_tutari:
        rol = en_ust_rol(rol, kupon_onay_rolu(kupon_tutari))
    return rol


def politika_istisnasi_mi(cayma: str, islem_tutari: float | None) -> bool:
    """POL-ESK-007 4.4: süreyi en fazla 2 gün aşan ve 2.500 TL üzeri cayma talebi → TL'ye istisna."""
    return cayma == "GRI" and (islem_tutari or 0) > GRI_ALAN_TUTAR


# --- Zorunlu eskalasyon ve güvenlik işaretleri (POL-ESK-007 Madde 6, 3.3) ---
ESKALASYON_KELIMELERI = {
    "HUKUK_KALITE": ["hakem heyeti", "avukat", "dava ", "dava acacag", "mahkeme", "savcilik", "resmi sikayet",
                     "yasal yollara", "hukuki"],
    "KVKK": ["kisisel veri", "verilerimin silin", "verilerimi silin", "kvkk"],
    "GUVENLIK": ["ele gecir", "ben vermedim", "bu siparisi ben", "dolandiric", "hesabima izinsiz"],
    "URUN_GUVENLIGI": ["duman", "yanik kokusu", "alev ", "alev aldi", "elektrik carp", "patladi", "yaralan", "kivilcim"],
}
INJECTION_KALIPLARI = ["onceki talimat", "talimatlari dikkate alma", "talimatlari yok say", "yetkili onayi gerekmez",
                       "onaylanmistir", "sistem notu", "ignore previous", "olarak isaretle", "onay seviyesini"]


def zorunlu_eskalasyonlar(mesaj: str, son_30_gun_sikayet: int = 0) -> list[str]:
    """Mesaj ve müşteri geçmişinden zorunlu eskalasyon birimleri (POL-ESK-007 6.1-6.5).
    son_30_gun_sikayet mevcut talep hariçtir; eşik mevcut talep dahil 3'tür."""
    m = normalize(mesaj)
    birimler = [b for b, kelimeler in ESKALASYON_KELIMELERI.items() if any(k in m for k in kelimeler)]
    if son_30_gun_sikayet + 1 >= SIKAYET_ESIGI:
        birimler.append("KALITE_KONTROL")
    return birimler


def injection_isareti(mesaj: str) -> bool:
    """POL-ESK-007 3.3: mesajdaki onay/talimat iddiaları onay yerine geçmez; işaretlenir ve kayda not düşülür."""
    m = normalize(mesaj)
    return any(k in m for k in INJECTION_KALIPLARI)


def bilgileri_hesapla(siparis: dict | None, musteri: dict | None, mesaj: str, bugun: date) -> dict:
    """Agent'ın 'bilgileri_hesapla' düğümü: LLM'e verilecek kesin bilgiler."""
    bilgi = {
        "zorunlu_eskalasyonlar": zorunlu_eskalasyonlar(mesaj, (musteri or {}).get("son_30_gun_sikayet", 0)),
        "injection_isareti": injection_isareti(mesaj),
        "siparis_var": siparis is not None,
    }
    if not siparis:
        return bilgi
    teslim = date.fromisoformat(siparis["teslim_tarihi"]) if siparis.get("teslim_tarihi") else None
    kargo = date.fromisoformat(siparis["kargo_tarihi"]) if siparis.get("kargo_tarihi") else None
    kamp = siparis.get("kampanya") or {}
    paylar = odenen_paylar(siparis["kalemler"], float(kamp.get("indirim_tutari", 0) or 0))
    bilgi.update({
        "durum": siparis["durum"],
        "odeme_yontemi": siparis["odeme_yontemi"],
        "taksit_sayisi": siparis["taksit_sayisi"],
        "kampanya": kamp.get("ad"),
        "onceki_degisim_sayisi": siparis["degisim_sayisi"],
        "telafi_kuponu_tl": siparis.get("telafi_kuponu_tl"),
        "kalemler": [
            {"kalem_no": k["kalem_no"], "urun": k["urun"], "urun_grubu": k["urun_grubu"],
             "odenen_pay_tl": paylar.get(k["kalem_no"], 0.0), "hediye": k.get("hediye", False),
             "cayma_istisnasi": k.get("cayma_istisnasi"), "garanti_ay": k.get("garanti_ay"),
             "onarim_sayisi": len(k.get("onarimlar", []))}
            for k in siparis["kalemler"]
        ],
        "siparis_toplam_odenen_tl": round(sum(paylar.values()), 2),
    })
    if teslim:
        gun = (bugun - teslim).days
        bilgi.update({
            "teslimden_gecen_gun": gun,
            "cayma_durumu": cayma_durumu(gun),
            "kusur_halinde_politika": kusur_kategorisi(gun),
            "degisim_suresi_icinde": gun <= DEGISIM_GUN,
            "garanti_icinde": any(k.get("garanti_ay") and gun <= k["garanti_ay"] * 30.4 for k in siparis["kalemler"]),
        })
    if kargo and not teslim:
        isg = is_gunu_say(kargo, bugun)
        bilgi.update({"kargodan_gecen_is_gunu": isg, "kargo_durumu": kargo_durumu(isg)})
    return bilgi
