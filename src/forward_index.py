import os
import json
import hashlib

from .preprocessing import iter_records, analyze_document


# ---------------- FILE FINGERPRINT ----------------

def file_fingerprint(path):
    """
    Create a SHA256 fingerprint for a file.
    This helps us check whether a file has changed.
    """

    h = hashlib.sha256()

    with open(path, 'rb') as f:

        # Read the file in small parts.
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)

    return h.hexdigest()


# ---------------- CREATE ONE FORWARD ENTRY ----------------

def make_forward_entry(record, lexicon):
    """
    Create one Forward Index entry for a review.

    Each term is stored as:
    [word_id, tf, in_title, first_pos]
    """

    # Get word information and document length.
    stats, doc_len = analyze_document(record)

    terms = []

    # Convert each word into its Lexicon word ID.
    for term, values in stats.items():

        # Get the word ID from the Lexicon.
        info = lexicon.get(term)

        if info is None:
            raise ValueError(
                f"word '{term}' in doc {record['doc_id']} is not in the Lexicon, "
                "rebuild the Lexicon from the same dataset"
            )

        word_id = info[0]

        # Get the word's statistics.
        tf, in_title, first_pos = values

        # Save the word information.
        terms.append([
            word_id,
            tf,
            in_title,
            first_pos
        ])

    # Sort terms by their word IDs.
    terms.sort(key=lambda item: item[0])

    # Save the review information.
    return {
        "doc_id": record["doc_id"],
        "rating": record["rating"],
        "helpful_vote": record["helpful_vote"],
        "timestamp": record["timestamp"],
        "title": record["title"],
        "doc_len": doc_len,
        "terms": terms
    }


# ---------------- BUILD FORWARD INDEX ----------------

def build_forward_index(
    source_path,
    lexicon,
    lexicon_path,
    forward_path,
    meta_path
):
    """
    Build the Forward Index from a JSONL dataset.
    Each review is saved as one JSON line.
    """

    num_docs = 0
    total_tokens = 0
    total_terms = 0
    max_doc_id = -1

    # Read reviews one at a time.
    with open(forward_path, 'w', encoding='utf-8') as out:

        for record in iter_records(source_path):

            # Create the Forward Index entry.
            entry = make_forward_entry(record, lexicon)

            # Save the entry as one JSON line.
            out.write(
                json.dumps(entry, separators=(',', ':')) + '\n'
            )

            # Update the counts.
            num_docs += 1
            total_tokens += entry["doc_len"]
            total_terms += len(entry["terms"])

            max_doc_id = max(max_doc_id, entry["doc_id"])

    # Calculate the average document length.
    avg_doc_len = total_tokens / max(num_docs, 1)

    # Save information about the Forward Index.
    meta = {
        "source": os.path.basename(source_path),
        "source_sha256": file_fingerprint(source_path),
        "num_docs": num_docs,
        "total_tokens": total_tokens,
        "avg_doc_len": avg_doc_len,
        "vocab_size": len(lexicon),
        "total_terms": total_terms,
        "next_doc_id": max_doc_id + 1,
        "lexicon_sha256": file_fingerprint(lexicon_path),
        "forward_size_bytes": os.path.getsize(forward_path)
    }

    # Save the metadata in a JSON file.
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=4)

    return meta


# ---------------- LOAD METADATA ----------------

def load_meta(path):
    """
    Load the saved Forward Index metadata.
    """

    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ---------------- CHECK FORWARD INDEX ----------------

def forward_index_is_current(
    source_path,
    lexicon_path,
    forward_path,
    meta_path
):
    """
    Check whether the saved Forward Index is still up to date.
    """

    # Check that both files exist.
    if not (
        os.path.exists(forward_path)
        and os.path.exists(meta_path)
    ):
        return False, "no saved forward index"

    # Load the saved metadata.
    meta = load_meta(meta_path)

    # Check the dataset name.
    if meta.get("source") != os.path.basename(source_path):
        return False, "built from a different source file"

    # Check whether the dataset has changed.
    if meta.get("source_sha256") != file_fingerprint(source_path):
        return False, "the dataset changed since it was built"

    # Check whether the Lexicon has changed.
    if meta.get("lexicon_sha256") != file_fingerprint(lexicon_path):
        return False, "the Lexicon changed since it was built"

    # Check whether the Forward Index file has changed.
    if meta.get("forward_size_bytes") != os.path.getsize(forward_path):
        return False, "the Forward Index file has changed or is incomplete"

    return True, "up to date"


# ---------------- READ FORWARD INDEX ----------------

def iter_forward_index(path):
    """
    Read the Forward Index one review at a time.
    """

    with open(path, 'r', encoding='utf-8') as f:

        for line in f:

            line = line.strip()

            # Skip empty lines.
            if not line:
                continue

            # Convert the JSON line into a Python dictionary.
            yield json.loads(line)