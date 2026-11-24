"""Agent'ın deterministik yardımcıları: PII maskeleme, atıf normalleştirme, yanıt temizliği (model gerektirmez)."""
import json
import unittest
from datetime import date
from unittest import mock

from config import DATA_DIR
from app import kurallar as K
from app.agent import graf
from app.agent.graf import atif_normalize, bilgi_metni, maskele, yanit_taslagi

P = [{"kod": "POL-HSR-004", "madde_no": 3, "etiket": "K1"}]


class TestAgentYardimci(unittest.TestCase):
    def test_maskeleme(self):
        m = maskele("IBAN: TR00 1234 5678 9012 3456 7890 12, kart 4543 1234 5678 9012, TC 12345678901, a@b.com")
        for gizli in ("TR00", "4543", "12345678901", "a@b.com"):
            self.assertNotIn(gizli, m)

    def test_atif_normalize(self):
        self.assertEqual(atif_normalize("x [POL-HSR-004 - Madde 3.3]", P), "x [K1]")
        self.assertEqual(atif_normalize("x [POL-IADE-001 Madde 6]", P), "x [POL-IADE-001 Madde 6]")

    def test_yanit_temizligi(self):
        s = {"oneri": {"musteri_yaniti": "İade uygundur [K1] (POL-HSR-004 Madde 3). Kod: GIZLI10. IBAN TR00 1234 5678 9012 3456 7890 12"},
             "guvenlik": {"uyarilar": []}}
        r = yanit_taslagi(s)
        for yasak in ("[K1]", "POL-HSR-004", "GIZLI10", "TR00"):
            self.assertNotIn(yasak, r["yanit_taslagi"])
        self.assertTrue(r["guvenlik"]["uyarilar"])

    def test_ekler_dogrulama_ve_bilgi_metni(self):
        b = K.bilgileri_hesapla(None, None, "Ürün kırık geldi", date(2026, 11, 23), ["fotograf", "uydurma<script>"])
        self.assertEqual(b["ekler"], ["fotograf"])          # bilinmeyen tür modele gitmez
        bos = K.bilgileri_hesapla(None, None, "Ürün kırık geldi", date(2026, 11, 23))
        with mock.patch.object(graf, "KARAR_TALIMAT_SURUMU", "v1"):   # v1 ölçümü ek bilgisi olmadan yapıldı
            self.assertNotIn("EKLEMİŞ", bilgi_metni(b))
            self.assertNotIn("eklenmemiş", bilgi_metni(bos))
        with mock.patch.object(graf, "KARAR_TALIMAT_SURUMU", "v3"):
            self.assertIn("EKLEMİŞ: fotoğraf", bilgi_metni(b))
            self.assertIn("eklenmemiş", bilgi_metni(bos))

    def test_ekler_veri_setinde_tanimli(self):
        veri = json.loads((DATA_DIR / "ornek_talepler.json").read_text(encoding="utf-8"))
        for t in veri["talepler"]:
            self.assertEqual(K.ekleri_dogrula(t["ekler"]), t["ekler"], t["id"])


if __name__ == "__main__":
    unittest.main()
