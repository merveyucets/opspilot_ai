"""LLM çıktısı doğrulama ve atıf kontrolü birim testleri (model gerektirmez)."""
import json
import unittest

from app.llm.siniflandir import KATEGORILER, dogrula
from app.rag.kalite import lexical_score, validate_citations

GECERLI = {"kategori": "IADE", "aciliyet": "ORTA", "duygu": "NOTR", "ozet": "İade talebi."}


class TestSiniflandirmaDogrulama(unittest.TestCase):
    def test_gecerli(self):
        self.assertEqual(dogrula(json.dumps(GECERLI))["kategori"], "IADE")

    def test_kategori_listesi_veriyle_ayni(self):
        from config import DATA_DIR
        veri = json.loads((DATA_DIR / "ornek_talepler.json").read_text(encoding="utf-8"))
        self.assertEqual({t["beklenen"]["kategori"] for t in veri["talepler"]}, set(KATEGORILER))

    def test_gecersiz_deger_reddedilir(self):
        for alan, deger in [("kategori", "ESKALASYON"), ("aciliyet", "ACIL"), ("duygu", "KIZGIN"), ("ozet", 5)]:
            with self.assertRaises(ValueError, msg=alan):
                dogrula(json.dumps({**GECERLI, alan: deger}))

    def test_bozuk_json(self):
        with self.assertRaises(json.JSONDecodeError):
            dogrula('{"kategori": "IADE"')


class TestKalite(unittest.TestCase):
    def test_atif(self):
        self.assertTrue(validate_citations("14 gün [K1].", ["K1", "K2"])["valid"])
        self.assertFalse(validate_citations("14 gün [K4].", ["K1", "K2"])["valid"])
        self.assertTrue(validate_citations("14 gün.", ["K1"])["missing"])

    def test_lexical_durak_kelime_ve_bonus(self):
        self.assertEqual(lexical_score("ve ile için", "herhangi"), 0.0)
        # sorgu kelimeleri {pol, iade, 001, madde, cayma}; içerikte yalnızca "cayma" → 1/5 + kod 0.3 + madde 0.3
        self.assertAlmostEqual(lexical_score("POL-IADE-001 madde 3 cayma", "cayma", "POL-IADE-001", 3), 0.8)


if __name__ == "__main__":
    unittest.main()
