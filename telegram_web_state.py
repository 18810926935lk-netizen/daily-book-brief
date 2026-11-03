"""Allowlist only the fresh WebA session's authentication data."""
import json
import re

ORIGIN = 'https://web.telegram.org'


def filter_state(state):
    entries = []
    for origin in state.get('origins', []):
        if origin.get('origin') != ORIGIN:
            continue
        for item in origin.get('localStorage', []):
            name, value = item['name'], item['value']
            if name == 'account1':
                account = json.loads(value)
                account = {k: v for k, v in account.items() if
                           k in ('dcId', 'userId', 'authKeyCreatedAt', 'tempAuthKey', 'isTest')
                           or re.fullmatch(r'dc[1-5]_auth_key', k)}
                if not account.get('userId') or not account.get('dcId'):
                    continue
                if not any(re.fullmatch(r'dc[1-5]_auth_key', k) for k in account):
                    continue
                value = json.dumps(account)
            elif name == 'user_auth':
                auth = json.loads(value)
                value = json.dumps({k: v for k, v in auth.items() if k in ('dcID', 'id', 'test')})
            elif name != 'dc' and not re.fullmatch(r'dc[1-5]_(auth_key|hash|server_salt)', name):
                continue
            entries.append({'name': name, 'value': value})
    if not any(x['name'] == 'account1' for x in entries):
        raise ValueError('fresh_account1_authorization_missing')
    return {'cookies': [], 'origins': [{'origin': ORIGIN, 'localStorage': entries}]}
