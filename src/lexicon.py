import json
from collections import Counter

from .preprocessing import iter_records, analyze_document


def build_lexicon(source_path, lexicon_path):
    """
    Build a Lexicon from a JSONL dataset.

    Format:
        {word: [id, df]}

    id = unique word ID assigned alphabetically.
    df = number of documents containing the word.
    """

    df = Counter()

    for record in iter_records(source_path):
        stats, _ = analyze_document(record)
        df.update(stats.keys())

    lexicon = {
        term: [i, df[term]]
        for i, term in enumerate(sorted(df))
    }

    with open(lexicon_path, 'w', encoding='utf-8') as f:
        json.dump(lexicon, f)

    return lexicon


def load_lexicon(path):
    """
    Load an existing Lexicon from a JSON file.

    Checks that the Lexicon uses the expected [id, df] format.
    """

    with open(path, 'r', encoding='utf-8') as f:
        lexicon = json.load(f)

    first = next(iter(lexicon.values()), None)

    if first is not None and (
        not isinstance(first, list) or len(first) != 2
    ):
        raise ValueError(
            "Invalid Lexicon format. Set REBUILD = True in Cell 2A."
        )

    return lexicon
