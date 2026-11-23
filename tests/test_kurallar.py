"""Deterministik kuralların 36 talebin beklenen sonuçlarına karşı testi (model gerektirmez)."""
import json
import unittest
from datetime import date

from config import DATA_DIR
from app import kurallar as K

TALEPLER = json.loads((DATA_DIR / "ornek_talepler.json").read_text(encoding="utf-8"))["talepler"]
SEED = json.loads((DATA_DIR / "siparisler_seed.json").read_text(encoding="utf-8"))
MUSTERI = {m["musteri_id"]: m for m in SEED["musteriler"]}
SIPARIS = {s["siparis_no"]: s for s in SEED["siparisler"]}


class TestEskalasyonVeInjection(unittest.TestCase):
    def test_36_talepte_zorunlu_eskalasyon(self):
        """Beklenen eskalasyon birimi (politika istisnası hariç) ile kural çıktısı birebir aynı."""
        for t in TALEPLER:
            beklenen = t["beklenen"]["eskalasyon_birimi"]
            beklenen = [] if beklenen in (None, "POLITIKA_ISTISNASI") else [beklenen]
            bulunan = K.zorunlu_eskalasyonlar(t["mesaj"], MUSTERI[t["musteri_id"]]["son_30_gun_sikayet"])
            self.assertEqual(sorted(bulunan), sorted(beklenen), t["id"])

    def test_injection_yalniz_d03(self):
        isaretli = [t["id"] for t in TALEPLER if K.injection_isareti(t["mesaj"])]
        self.assertEqual(isaretli, ["D03"])


class TestTarih(unittest.TestCase):
    def test_cayma_sinirlari(self):
        self.assertEqual([K.cayma_durumu(g) for g in (14, 15, 16, 17)], ["SURE_ICI", "GRI", "GRI", "SURE_DISI"])

    def test_talep_gunleri_beklenenle_uyumlu(self):
        """T03 (14. gün) süre içi, T30 (16. gün) gri alan, T11 (19) ve D03 (25) süre dışı."""
        for tid, beklenen in [("T03", "SURE_ICI"), ("T30", "GRI"), ("T11", "SURE_DISI"), ("D03", "SURE_DISI")]:
            sip = SIPARIS[next(t["siparis_no"] for t in TALEPLER if t["id"] == tid)]
            self.assertEqual(K.cayma_durumu(sip["teslim_gun_once"]), beklenen, tid)

    def test_kusur_politikasi(self):
        self.assertEqual(K.kusur_kategorisi(4), "HASARLI_URUN")   # T07
        self.assertEqual(K.kusur_kategorisi(300), "GARANTI")      # D02

    def test_is_gunu_pazar_ve_tatil_sayilmaz(self):
        # 2026-11-21 cumartesi → 2026-11-23 pazartesi: pazar sayılmaz, cumartesi sayılır
        self.assertEqual(K.is_gunu_say(date(2026, 11, 20), date(2026, 11, 23)), 2)
        self.assertEqual(K.is_gunu_say(date(2026, 10, 28), date(2026, 10, 29)), 0)   # 29 Ekim

    def test_kargo_durumu(self):
        self.assertEqual([K.kargo_durumu(g) for g in (7, 8, 15)], ["NORMAL", "GECIKMIS", "KAYIP"])


class TestTutarVeOnay(unittest.TestCase):
    def test_odenen_paylar_politika_ornekleri(self):
        sp = SIPARIS["SP-2009"]   # 3 Al 2 Öde, POL-KMP-009 4.3
        self.assertEqual(K.odenen_paylar(sp["kalemler"], 200.0), {1: 311.11, 2: 233.33, 3: 155.56})
        sp = SIPARIS["SP-2026"]   # sepet indirimi, POL-KMP-009 3.2
        self.assertEqual(K.odenen_paylar(sp["kalemler"], 400.0), {1: 800.0, 2: 400.0, 3: 400.0})
        sp = SIPARIS["SP-2007"]   # hediye ürün dağıtıma girmez
        self.assertEqual(K.odenen_paylar(sp["kalemler"], 0.0), {1: 4200.0})

    def test_onay_esikleri(self):
        self.assertEqual([K.onay_rolu(x) for x in (2500, 2500.01, 15000, 15000.01)],
                         ["DESTEK_UZMANI", "TAKIM_LIDERI", "TAKIM_LIDERI", "OPERASYON_MUDURU"])

    def test_36_talepte_gerekli_onay(self):
        """Beklenen öneri ve işlem tutarı verildiğinde kural, beklenen onay rolünü üretir."""
        for t in TALEPLER:
            b = t["beklenen"]
            istisna = b["eskalasyon_birimi"] == "POLITIKA_ISTISNASI"
            kupon = b["islem_tutari"] if t["id"] == "T10" else None
            tutar = None if kupon else b["islem_tutari"]
            self.assertEqual(K.gerekli_onay(b["oneri"], tutar, istisna, kupon), b["gerekli_onay"], t["id"])

    def test_politika_istisnasi_kurali(self):
        self.assertTrue(K.politika_istisnasi_mi("GRI", 3200))      # T30
        self.assertFalse(K.politika_istisnasi_mi("GRI", 1650))
        self.assertFalse(K.politika_istisnasi_mi("SURE_DISI", 5600))   # D03

    def test_bilgileri_hesapla(self):
        sp = dict(SIPARIS["SP-2009"], teslim_tarihi="2026-11-17", kargo_tarihi="2026-11-15")
        b = K.bilgileri_hesapla(sp, MUSTERI["MUS-109"], "Yoga matını iade etmek istiyorum", date(2026, 11, 23))
        self.assertEqual(b["teslimden_gecen_gun"], 6)
        self.assertEqual(b["cayma_durumu"], "SURE_ICI")
        self.assertEqual(b["kalemler"][0]["odenen_pay_tl"], 311.11)
        self.assertEqual(b["zorunlu_eskalasyonlar"], [])


if __name__ == "__main__":
    unittest.main()
