import json
import unittest
from telegram_web_state import filter_state


class StateTests(unittest.TestCase):
    def test_removes_chat_data_other_accounts_origins_cookies(self):
        state = {'cookies': [{'value': 'private'}], 'origins': [
            {'origin': 'https://other.invalid', 'localStorage': [{'name': 'dc', 'value': 'bad'}]},
            {'origin': 'https://web.telegram.org', 'indexedDB': ['private'], 'localStorage': [
                {'name': 'account1', 'value': json.dumps({'userId': '123', 'dcId': 2,
                 'dc2_auth_key': 'synthetic', 'chats': 'private', 'phone': 'private'})},
                {'name': 'account2', 'value': 'private'},
                {'name': 'GramJs', 'value': 'private'},
                {'name': 'dc', 'value': '2'}]}]}
        result = filter_state(state)
        self.assertNotIn('private', json.dumps(result))
        self.assertEqual(result['cookies'], [])
        self.assertEqual(len(result['origins']), 1)
        self.assertEqual(filter_state(result), result)

    def test_rejects_missing_or_locked_login(self):
        with self.assertRaises(ValueError):
            filter_state({'origins': []})


if __name__ == '__main__':
    unittest.main()
