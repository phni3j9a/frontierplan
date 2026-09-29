import unittest
from normalize import normalize_label

class NormalizeTests(unittest.TestCase):
    def test_whitespace(self):
        self.assertEqual(normalize_label("  hello\t world  "), "hello world")
    def test_empty(self):
        self.assertEqual(normalize_label("   "), "")

    def test_casefold_unicode(self):
        self.assertEqual(normalize_label("  HELLO\tStraße  "), "hello strasse")

if __name__ == "__main__":
    unittest.main()
