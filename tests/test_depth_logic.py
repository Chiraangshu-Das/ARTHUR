import unittest

from visionguide.depth import DepthReading, MotionRiskAnalyzer
from visionguide.perception import Detection


def central_person():
    return Detection(
        label="person", confidence=0.9, x1=280, y1=80, x2=360, y2=220,
        center_x=320, center_y=150, direction="centre", track_id=9,
    )


class DepthMotionLogicTests(unittest.TestCase):
    def reading(self, distance, now, spread=0.05):
        return DepthReading("person", 9, distance, distance, spread, now)

    def test_closing_candidate_can_raise_depth_alert(self):
        analyzer = MotionRiskAnalyzer()
        det = central_person()
        self.assertEqual(analyzer.update([det], {("person", 9): self.reading(4.7, 10.0)}, 640, 10.0), [])
        self.assertEqual(analyzer.update([det], {("person", 9): self.reading(3.8, 10.7)}, 640, 10.7), [])
        alerts = analyzer.update([det], {("person", 9): self.reading(2.9, 11.4)}, 640, 11.4)
        self.assertEqual(len(alerts), 1)
        self.assertIn("Possible approaching person", alerts[0])
        self.assertIn("uncertain", alerts[0])

    def test_no_alert_for_receding_object(self):
        analyzer = MotionRiskAnalyzer()
        det = central_person()
        analyzer.update([det], {("person", 9): self.reading(2.9, 10.0)}, 640, 10.0)
        analyzer.update([det], {("person", 9): self.reading(3.8, 10.7)}, 640, 10.7)
        alerts = analyzer.update([det], {("person", 9): self.reading(4.7, 11.4)}, 640, 11.4)
        self.assertEqual(alerts, [])

    def test_high_depth_spread_is_not_used_for_alert(self):
        analyzer = MotionRiskAnalyzer()
        det = central_person()
        values = [4.7, 3.8, 2.9]
        results = []
        for index, distance in enumerate(values):
            now = 10.0 + index * 0.7
            results.extend(analyzer.update([det], {("person", 9): self.reading(distance, now, spread=0.5)}, 640, now))
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
