import json
import time
import re
from functools import lru_cache

import nltk
from nltk.stem import PorterStemmer


# ---------------- TOKENIZER ----------------

_stopwords = None


def get_stopwords():
    # Load the stopword list only the first time it is needed.
    global _stopwords

    if _stopwords is None:
        nltk.download('stopwords', quiet=True)
        from nltk.corpus import stopwords
        _stopwords = set(stopwords.words('english'))

    return _stopwords


_stemmer = PorterStemmer()


@lru_cache(maxsize=None)
def stem_word(word):
    return _stemmer.stem(word)


WORD_PATTERN = re.compile(r"[a-z0-9']+")


def tokenize(text, remove_stopwords=False):
    """Return a list of stemmed lowercase tokens.
    Stopwords are KEPT by default so 'data structures and algorithms'
    can match on 'and' (spec Requirement 5)."""

    tokens = []
    stop = get_stopwords() if remove_stopwords else ()

    for w in WORD_PATTERN.findall(text.lower()):
        w = w.strip("'")

        if not w:
            continue

        if w in stop:
            continue

        tokens.append(stem_word(w))

    return tokens


# ---------------- RECORD NORMALIZATION ----------------

DEFAULT_RATING = 3.0


def _to_number(value, cast, default):
    """Convert value using cast (int or float).
    Returns default if value is None or cannot be converted."""

    if value is None:
        return default

    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


def normalize_record(raw, doc_id=None):
    """Turn a raw dict into a clean record with all six fields.
    Raises ValueError if the record has no usable text or no doc_id."""

    if not isinstance(raw, dict):
        raise ValueError("record is not a dict")

    text = raw.get('text')
    text = text.strip() if isinstance(text, str) else ''

    if not text:
        raise ValueError("record has no text")

    title = raw.get('title')
    title = title.strip() if isinstance(title, str) else ''

    if doc_id is None:
        doc_id = _to_number(raw.get('doc_id'), int, None)

    if doc_id is None:
        raise ValueError("record has no doc_id")

    rating = _to_number(raw.get('rating'), float, DEFAULT_RATING)
    rating = min(5.0, max(1.0, rating))

    votes = _to_number(raw.get('helpful_vote'), int, 0)
    votes = max(0, votes)

    now_ms = int(time.time() * 1000)
    timestamp = _to_number(raw.get('timestamp'), int, now_ms)

    return {
        "doc_id": doc_id,
        "title": title,
        "text": text,
        "rating": rating,
        "helpful_vote": votes,
        "timestamp": timestamp,
    }


# ---------------- DOCUMENT ANALYSIS ----------------

def analyze_document(record):
    """Return (stats, doc_len) for one clean record.
    stats maps each term to [tf, in_title, first_pos]:
      tf        = how many times the term appears in the text
      in_title  = 1 if the term also appears in the title, else 0
      first_pos = index of the first occurrence in the text (-1 if title-only)
    doc_len = number of tokens in the text."""

    text_tokens = tokenize(record['text'])

    stats = {}

    for pos, term in enumerate(text_tokens):
        if term in stats:
            stats[term][0] += 1
        else:
            stats[term] = [1, 0, pos]

    for term in set(tokenize(record['title'])):
        if term in stats:
            stats[term][1] = 1
        else:
            stats[term] = [0, 1, -1]

    return stats, len(text_tokens)


# ---------------- DATASET READING ----------------

def iter_records(path):
    """Yield clean records from a JSONL file, one at a time.
    Bad lines (invalid JSON, no text, no doc_id) are skipped and counted."""

    skipped = 0

    with open(path, 'r', encoding='utf-8') as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                yield normalize_record(json.loads(line))

            except ValueError as e:
                skipped += 1

                if skipped <= 5:
                    print(f"Skipped line {line_no}: {e}")

    if skipped:
        print(f"Total skipped lines: {skipped}")
