"""Agent'ın deterministik yardımcıları: PII maskeleme, atıf normalleştirme, yanıt temizliği (model gerektirmez)."""
import unittest

from app.agent.graf import atif_normalize, maskele, yanit_taslagi

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


if __name__ == "__main__":
    unittest.main()
