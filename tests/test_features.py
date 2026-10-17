"""Check timeline date integrity and inclusive calendar-day geometry."""
import json
from datetime import date
from pathlib import Path
import unittest

from features.build import display_dates, render_table


class FeatureTimelineTests(unittest.TestCase):
    def test_sample_dates_leave_recorded_history_intact(self):
        features = json.loads(Path('features/features.json').read_text())
        self.assertTrue(all(date.fromisoformat(feature['requested_on']) <= date.today() for feature in features if feature.get('requested_on')))
        self.assertEqual(next(f for f in features if f['id']=='snake-game')['completed_on'], '2026-10-16')
        groundwork = next(feature for feature in features if feature['id'] == 'web-hosting')
        self.assertIsNone(groundwork['requested_on'])
        self.assertIsNone(groundwork['completed_on'])
        email = next(feature for feature in features if feature['id'] == 'project-email')
        self.assertEqual(email['status'], 'shipped')
        self.assertIsNotNone(display_dates(email)[1])
        first = next(feature for feature in features if feature['id'] == 'snake-game')
        self.assertEqual(display_dates(first), (date(2026, 10, 1), date(2026, 10, 10)))
        self.assertEqual(first['completed_on'], '2026-10-16')

    def test_gantt_includes_first_and_last_days(self):
        task = {'title': 'One task', 'description': 'Short.', 'status': 'shipped', 'requested_on': '2026-10-01', 'completed_on': '2026-10-03'}
        chart = render_table([task], 'Completed', date(2026, 10, 16))
        self.assertIn('left:0.000%;width:18.750%', chart)
        task['requested_on'] = task['completed_on'] = '2026-10-16'
        chart = render_table([task], 'Completed', date(2026, 10, 16))
        self.assertIn('left:93.750%;width:6.250%', chart)

    def test_queued_tasks_have_no_completion_or_promised_bar(self):
        task = {'title': 'Next idea', 'description': 'Short.', 'status': 'queued', 'requested_on': '2026-10-16'}
        chart = render_table([task], 'To-do', date(2026, 10, 16))
        self.assertIn('Not yet', chart)
        self.assertIn('class="gantt-queued"', chart)
        self.assertNotIn('class="gantt-bar"', chart)
        task['completed_on'] = '2026-10-15'
        with self.assertRaises(ValueError):
            display_dates(task)


if __name__ == '__main__':
    unittest.main()
