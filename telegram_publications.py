"""Conservative filename classification; dates are candidates, not verified mastheads."""
import re
from datetime import date, timedelta

# Specific titles precede broader aliases. Never match a generic 'Times'.
TITLES = [
    ('nytimes-book-review', 'The New York Times Book Review', r'new york times book review|nyt book review'),
    ('wsj', 'The Wall Street Journal', r'wall street journal|\bwsj\b'),
    ('washington-post', 'The Washington Post', r'washington post|\bwapo\b'),
    ('nytimes', 'The New York Times', r'new york times|\bnyt\b'),
    ('economist', 'The Economist', r'\beconomist\b'),
    ('financial-times', 'Financial Times', r'financial times|\bft\b'),
    ('guardian', 'The Guardian', r'\bguardian\b'),
    ('new-yorker', 'The New Yorker', r'new yorker|newyorker'),
    ('nyrb', 'The New York Review of Books', r'new york review of books|\bnyrb\b'),
    ('lrb', 'London Review of Books', r'london review of books|\blrb\b'),
    ('tls', 'The Times Literary Supplement', r'times literary supplement|\btls\b'),
    ('atlantic', 'The Atlantic', r'\batlantic\b'),
    ('literary-review', 'Literary Review', r'\bliterary review\b'),
    ('publishers-weekly', 'Publishers Weekly', r'publishers weekly'),
]
MONTHS = {m: i for i, m in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}


def issue_date(filename, today):
    stem = re.sub(r'\.(pdf|docx)$', '', filename, flags=re.I)
    def valid(y, m, d):
        try:
            result = date(int(y), int(m), int(d))
            return result if today - timedelta(days=45) <= result <= today + timedelta(days=14) else None
        except ValueError:
            return None
    for pattern, order in [
        (r'(?<!\d)(20\d{2})[ ._\-/]([01]?\d)[ ._\-/]([0-3]?\d)(?!\d)', 'ymd'),
        (r'(?<!\d)([0-3]?\d)[ ._\-/]([01]?\d)[ ._\-/](20\d{2})(?!\d)', 'dmy'),
        (r'(?<!\d)(20\d{2})([01]\d)([0-3]\d)(?!\d)', 'ymd')]:
        match = re.search(pattern, stem)
        if match:
            a, b, c = match.groups()
            return valid(a, b, c) if order == 'ymd' else valid(c, b, a)
    month = r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    match = re.search(month + r'[\s._-]+(\d{1,2})(?:st|nd|rd|th)?[,\s._-]+(20\d{2})', stem, re.I)
    if match:
        m, d, y = match.groups()
        return valid(y, MONTHS[m[:3].lower()], d)
    match = re.search(r'(\d{1,2})[\s._-]+' + month + r'[,\s._-]+(20\d{2})', stem, re.I)
    if match:
        d, m, y = match.groups()
        return valid(y, MONTHS[m[:3].lower()], d)
    # Channel's observed DDMM convention (e.g. The Economist_3110.pdf).
    match = re.search(r'(?:^|[ _.-])(\d{2})(\d{2})(?=$|[ _.-])', stem)
    if match:
        d, m = match.groups()
        dates = [valid(y, m, d) for y in (today.year-1, today.year, today.year+1)]
        dates = [x for x in dates if x]
        if dates:
            return min(dates, key=lambda x: abs((x-today).days))
    match = re.search(month + r'[\s._-]+(20\d{2})', stem, re.I)
    if match:
        m, y = match.groups()
        return valid(y, MONTHS[m[:3].lower()], 1)  # Month-only candidate, not an asserted day.
    return None


def classify(row, today):
    name = row['filename']
    if not name.lower().endswith(('.pdf', '.docx')):
        return None
    normalized = re.sub(r'[_\W]+', ' ', name.lower())
    for rank, (key, title, pattern) in enumerate(TITLES):
        if re.search(pattern, normalized):
            issue = issue_date(name, today)
            if not issue and key != 'financial-times':
                return None
            return {**row, 'publication': title, 'rank': rank,
                    'issue_date_candidate': issue.isoformat() if issue else '',
                    'issue_key': key + ':' + (issue.isoformat() if issue else 'undated')}
    return None


def select_issues(rows, seen, today, limit=12):
    grouped = {}
    for row in rows:
        candidate = classify(row, today)
        if candidate:
            grouped.setdefault(candidate['issue_key'], []).append(candidate)
    # One latest issue per title in each run; regional variants are fallbacks only.
    latest = {}
    for variants in grouped.values():
        variants.sort(key=lambda v: int(v['id']), reverse=True)
        if not variants[0]['issue_date_candidate']:
            newest_id = int(variants[0]['id'])
            variants = [v for v in variants if newest_id - int(v['id']) <= 4]
            for v in variants:
                v['issue_key'] += ':' + str(newest_id)
        item = variants[0]
        key = item['publication']
        if key not in latest or item['issue_date_candidate'] > latest[key][0]['issue_date_candidate']:
            latest[key] = variants
    return sorted([v for v in latest.values() if v[0]['issue_key'] not in seen],
                  key=lambda v: v[0]['rank'])[:limit]
