import json
import unittest
from pathlib import Path

N8N_DIR = Path(__file__).resolve().parent.parent / "automation" / "n8n"


class N8nFlowsTest(unittest.TestCase):
    def test_flows_valid_and_connected(self):
        for fname in ("weekly_digest.json", "low_confidence_alert.json"):
            p = N8N_DIR / fname
            self.assertTrue(p.exists(), f"missing {p}")
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertTrue(data.get("name"))
            nodes = data.get("nodes") or []
            self.assertGreaterEqual(len(nodes), 3)
            names = {n["name"] for n in nodes}
            conns = data.get("connections") or {}
            self.assertTrue(conns)
            for src, branches in conns.items():
                self.assertIn(src, names)
                for targets in branches.get("main", []):
                    for edge in targets:
                        self.assertIn(edge["node"], names)

    def test_expected_endpoints_and_triggers(self):
        digest = (N8N_DIR / "weekly_digest.json").read_text(encoding="utf-8")
        self.assertIn("/teacher/summary", digest)

        alert = json.loads((N8N_DIR / "low_confidence_alert.json").read_text(encoding="utf-8"))
        types = {n["type"] for n in alert["nodes"]}
        self.assertIn("n8n-nodes-base.webhook", types)


if __name__ == "__main__":
    unittest.main()

