"""SQLite katmanı testleri: seed, idempotency, tek kullanımlık onay token'ı ve rol yetkisi (altın kural 2)."""
import tempfile
import unittest
from datetime import date
from pathlib import Path

from app import veritabani as V


class TestVeritabani(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.eski = V.DB_PATH
        V.DB_PATH = Path(self.tmp.name) / "test.sqlite3"
        V.seed(date(2026, 11, 23))

    def tearDown(self):
        V.DB_PATH = self.eski
        self.tmp.cleanup()

    def karar(self, talep_no, token, karar="ONAYLA", gerekli="DESTEK_UZMANI", key="k1", yanit="taslak"):
        return V.karar_kaydet(talep_no, karar, token, gerekli, "IADE_KABUL", "taslak", yanit, None, "g", "POL-IADE-001 Madde 3", key)

    def test_seed_tarihleri(self):
        s = V.siparis_getir("SP-2003")
        self.assertTrue(s["bulundu"])
        self.assertEqual(s["siparis"]["teslim_tarihi"], "2026-11-09")     # 14 gün önce
        self.assertNotIn("eposta", s["musteri"])                           # kişisel veri dönmez
        self.assertFalse(V.siparis_getir("SP-9999")["bulundu"])

    def test_talep_idempotent(self):
        a = V.talep_kaydet("İade istiyorum", "MUS-101", "SP-2001", "WEB_FORM", "op-1")
        b = V.talep_kaydet("İade istiyorum", "MUS-101", "SP-2001", "WEB_FORM", "op-1")
        self.assertEqual(a["talep_no"], b["talep_no"])
        self.assertTrue(b["idempotent"])

    def test_token_olmadan_karar_yok(self):
        t = V.talep_kaydet("İade", "MUS-101", "SP-2001", "WEB_FORM", "op-2")["talep_no"]
        with self.assertRaises(PermissionError):
            self.karar(t, "uydurma-token")
        self.assertEqual(V.talep_getir(t)["kararlar"], [])

    def test_token_tek_kullanimlik(self):
        t = V.talep_kaydet("İade", "MUS-101", "SP-2001", "WEB_FORM", "op-3")["talep_no"]
        token = V.onay_token_uret(t, "ayse", "DESTEK_UZMANI")
        self.assertTrue(self.karar(t, token)["kaydedildi"])
        with self.assertRaises(PermissionError):
            self.karar(t, token, key="k2")
        self.assertEqual(V.talep_getir(t)["talep"]["durum"], "KAPANDI")

    def test_yetersiz_rol_onaylayamaz_ama_eskale_edebilir(self):
        t = V.talep_kaydet("Dizüstü iade", "MUS-102", "SP-2002", "E_POSTA", "op-4")["talep_no"]
        token = V.onay_token_uret(t, "ayse", "DESTEK_UZMANI")
        with self.assertRaises(PermissionError):
            self.karar(t, token, gerekli="OPERASYON_MUDURU")
        token2 = V.onay_token_uret(t, "ayse", "DESTEK_UZMANI")
        r = self.karar(t, token2, karar="ESKALE_ET", gerekli="OPERASYON_MUDURU", key="k5")
        self.assertEqual(r["durum"], "ESKALE_EDILDI")

    def test_duzenleme_kaydedilir(self):
        t = V.talep_kaydet("İade", "MUS-101", "SP-2001", "WEB_FORM", "op-6")["talep_no"]
        token = V.onay_token_uret(t, "ayse", "DESTEK_UZMANI")
        self.karar(t, token, karar="DUZENLE_ONAYLA", yanit="düzenlenmiş metin")
        self.assertEqual(V.talep_getir(t)["kararlar"][0]["duzenlendi"], 1)


if __name__ == "__main__":
    unittest.main()
