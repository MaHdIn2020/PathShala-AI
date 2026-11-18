import unittest

from pathshala.clustering import cluster_records


class ClusteringTest(unittest.TestCase):
    def test_cluster_records_groups_similar_bangla_questions(self):
        recs = [
            {"question": "ভগ্নাংশের যোগ করার নিয়ম কী?", "topic": "ভগ্নাংশ", "refused": False},
            {"question": "প্রকৃত ও অপ্রকৃত ভগ্নাংশ কাকে বলে?", "topic": "ভগ্নাংশ", "refused": False},
            {"question": "মিশ্র ভগ্নাংশ কীভাবে ভাঙাতে হয়?", "topic": "ভগ্নাংশ", "refused": False},
            {"question": "ভগ্নাংশের বিয়োগ কীভাবে করে?", "topic": "ভগ্নাংশ", "refused": False},
            {"question": "খাদ্যশৃঙ্খল ও খাদ্যজাল কী?", "topic": "আমাদের পরিবেশ", "refused": False},
            {"question": "উদ্ভিদ ও প্রাণী কীভাবে নির্ভরশীল?", "topic": "আমাদের পরিবেশ", "refused": True},
            {"question": "খাদ্যজাল সম্পর্কে লেখো", "topic": "আমাদের পরিবেশ", "refused": False},
            {"question": "আমাদের পরিবেশের উপাদান কী কী?", "topic": "আমাদের পরিবেশ", "refused": False},
            {"question": "মহাস্থানগড় কোথায় অবস্থিত?", "topic": "ঐতিহাসিক স্থান", "refused": False},
            {"question": "লালবাগ কেল্লা কোথায় অবস্থিত?", "topic": "ঐতিহাসিক স্থান", "refused": True},
            {"question": "মহাস্থানগড় কেন বিখ্যাত?", "topic": "ঐতিহাসিক স্থান", "refused": False},
            {"question": "লালবাগ কেল্লার ইতিহাস কী?", "topic": "ঐতিহাসিক স্থান", "refused": False},
        ]
        clusters = cluster_records(recs, k=3)
        self.assertEqual(len(clusters), 3)
        self.assertEqual(sum(c["size"] for c in clusters), 12)
        self.assertEqual(sum(c["refused"] for c in clusters), 2)
        for c in clusters:
            self.assertTrue(c["label"])
            self.assertGreaterEqual(c["refusal_rate"], 0.0)
            self.assertLessEqual(c["refusal_rate"], 1.0)

    def test_cluster_records_handles_empty_and_clamps_k(self):
        self.assertEqual(cluster_records([]), [])
        self.assertEqual(cluster_records([{"question": "   "}]), [])

        recs = [{"question": f"প্রশ্ন নম্বর {i} পাঠ্যবইয়ের অংশ", "refused": False} for i in range(15)]
        clusters = cluster_records(recs, k=20)
        self.assertLessEqual(len(clusters), 8)

    def test_cluster_records_with_custom_llm_label(self):
        recs = [
            {"question": "গুণ্য কাকে বলে?", "topic": "গুণ ও ভাগ", "refused": False},
            {"question": "গুণক কাকে বলে?", "topic": "গুণ ও ভাগ", "refused": False},
        ]
        clusters = cluster_records(recs, k=2, llm_fn=lambda s, u, m, mt: ("গুণ পরিচিতি", {}), model="fast")
        self.assertEqual(clusters[0]["label"], "গুণ পরিচিতি")


if __name__ == "__main__":
    unittest.main()

