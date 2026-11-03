import unittest
from datetime import date
from telegram_publications import classify, issue_date, select_issues


class PublicationTests(unittest.TestCase):
    today = date(2026, 11, 3)

    def test_regional_versions_group_and_seen_issue_skips(self):
        rows = [{'id': str(i), 'filename': name} for i, name in enumerate([
            'The Economist Europe 2026-10-31.pdf', 'The Economist US 2026-10-31.pdf',
            'The Economist_3110.pdf', 'The Economist_2410.pdf', 'The New Yorker November 9 2026.pdf'])]
        result = select_issues(rows, {}, self.today)
        self.assertEqual(len(result), 2)
        self.assertEqual(len(result[0]), 3)
        self.assertEqual(len(select_issues(rows, {'economist:2026-10-31': {}}, self.today)), 1)

    def test_undated_ft_only_latest_upload_group_and_monthly_title(self):
        rows = [{'id': str(i), 'filename': 'FT ' + edition + '.pdf'}
                for i, edition in [(100, 'UK'), (101, 'US'), (102, 'EU'), (50, 'UK')]]
        result = select_issues(rows, {}, self.today)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]), 3)
        self.assertEqual(result[0][0]['issue_date_candidate'], '')
        self.assertEqual(issue_date('The Atlantic_Nov 2026.pdf', self.today), date(2026,11,1))

    def test_unknown_dates_titles_and_invalid_dates_are_not_guessed(self):
        for name in ['Times 2026-11-03.pdf', 'The Economist latest.pdf',
                     'The Economist 31.11.2026.pdf', 'The Economist 2020-11-03.pdf']:
            self.assertIsNone(classify({'filename': name}, self.today))

    def test_date_variants_and_year_boundary(self):
        for name in ['WSJ_2026.11.03.pdf', 'WSJ_03-11-2026.pdf', 'WSJ_20261103.pdf',
                     'WSJ_03 November 2026.pdf', 'WSJ_0311.pdf']:
            self.assertEqual(issue_date(name, self.today), self.today)
        self.assertEqual(issue_date('Economist_3112.pdf', date(2027,1,2)), date(2026,12,31))


if __name__ == '__main__':
    unittest.main()
