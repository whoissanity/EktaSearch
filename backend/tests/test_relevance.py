"""Unittests for search relevance scoring (run from backend: python -m unittest discover -s tests)."""
import unittest

from app.services.relevance import relevance_score


class TestRelevance(unittest.TestCase):
    def test_gpu_query_prefers_gpu_title_over_mouse(self):
        q = "4070 ti"
        gpu = relevance_score(q, "NVIDIA GeForce RTX 4070 Ti 12GB Graphics Card", None)
        mouse = relevance_score(q, "Logitech G502 Gaming Mouse", None)
        self.assertGreater(gpu, mouse)

    def test_phrase_in_title_scores_high(self):
        q = "b550 motherboard"
        hit = relevance_score(q, "MSI B550M PRO-VDH Motherboard", None)
        miss = relevance_score(q, "USB 3.0 Cable", None)
        self.assertGreater(hit, miss)

    def test_numeric_model_in_query(self):
        q = "7600x"
        cpu = relevance_score(q, "AMD Ryzen 5 7600X Processor", None)
        self.assertGreater(cpu, 0.0)


if __name__ == "__main__":
    unittest.main()
