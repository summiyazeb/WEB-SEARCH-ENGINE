import os
import json
import tempfile
from array import array

from .forward_index import iter_forward_index, file_fingerprint


# ---------------- COLLECT POSTINGS ----------------

def collect_postings(forward_path, lexicon):
    """
    Read the Forward Index and collect postings for every word.
    """

    postings = {}
    num_postings = 0
    num_docs = 0
    last_doc_id = -1

    # Store the expected document frequency for each word ID.
    expected_df = {}

    for word, info in lexicon.items():

        word_id, df = info

        if word_id in expected_df:
            raise ValueError(f"Duplicate word ID: {word_id}")

        expected_df[word_id] = df

    # Read one review at a time from the Forward Index.
    for entry in iter_forward_index(forward_path):

        doc_id = entry["doc_id"]

        # Make sure document IDs are in increasing order.
        if doc_id <= last_doc_id:
            raise ValueError(
                f"doc_id {doc_id} comes after {last_doc_id}. "
                "The Forward Index must have unique, increasing doc_ids."
            )

        last_doc_id = doc_id
        num_docs += 1

        previous_word_id = -1

        # Get the words and their information from this review.
        for word_id, tf, in_title, first_pos in entry["terms"]:

            # Make sure the word exists in the Lexicon.
            if word_id not in expected_df:
                raise ValueError(
                    f"Word ID {word_id} in document {doc_id} "
                    "does not exist in the Lexicon."
                )

            # Make sure word IDs are sorted.
            if word_id <= previous_word_id:
                raise ValueError(
                    f"Word IDs are not sorted in document {doc_id}."
                )

            previous_word_id = word_id

            # Create an array when we find a word for the first time.
            if word_id not in postings:
                postings[word_id] = array('i')

            # Add the document ID and word information.
            postings[word_id].extend([
                doc_id,
                tf,
                in_title,
                first_pos
            ])

            num_postings += 1

    # Stop if the Forward Index has no records.
    if not postings:
        raise ValueError("The Forward Index is empty.")

    # Compare posting counts with the Lexicon document frequencies.
    for word, info in lexicon.items():

        word_id, expected_count = info
        actual_count = len(postings.get(word_id, [])) // 4

        if actual_count != expected_count:
            raise ValueError(
                f"DF mismatch for '{word}': "
                f"Lexicon has {expected_count}, "
                f"Inverted Index has {actual_count}."
            )

    return postings, num_docs, num_postings


# ---------------- WRITE INVERTED INDEX ----------------

def write_inverted_index(postings, inverted_path):
    """
    Write one word per JSONL line in word ID order.
    """

    # Create the output folder if it does not exist.
    folder = os.path.dirname(inverted_path)

    if folder:
        os.makedirs(folder, exist_ok=True)

    # Create a temporary file for writing.
    fd, temp_path = tempfile.mkstemp(
        dir=folder or ".",
        prefix=".inverted-",
        suffix=".tmp"
    )

    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:

            # Write words in increasing word ID order.
            for word_id in sorted(postings):

                # Convert the posting array into comma-separated numbers.
                numbers = ','.join(map(str, postings[word_id]))

                # Save the word ID and its flat posting list.
                out.write(f"[{word_id},[{numbers}]]\n")

        # Replace the old file after writing is complete.
        os.replace(temp_path, inverted_path)

    except BaseException:
        # Remove the temporary file if something goes wrong.
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


# ---------------- SAVE METADATA ----------------

def write_json_safely(data, path):
    """
    Write a JSON file using a temporary file.
    """

    # Create the folder if it does not exist.
    folder = os.path.dirname(path)

    if folder:
        os.makedirs(folder, exist_ok=True)

    # Create a temporary file for the metadata.
    fd, temp_path = tempfile.mkstemp(
        dir=folder or ".",
        prefix=".meta-",
        suffix=".tmp"
    )

    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

        # Replace the old metadata file.
        os.replace(temp_path, path)

    except BaseException:
        # Remove the temporary file if something goes wrong.
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


# ---------------- BUILD INVERTED INDEX ----------------

def build_inverted_index(
    forward_path,
    lexicon,
    lexicon_path,
    inverted_path,
    meta_path
):
    """
    Build the Inverted Index using the saved Forward Index.
    """

    # Collect all word postings from the Forward Index.
    postings, num_docs, num_postings = collect_postings(
        forward_path,
        lexicon
    )

    # Save the Inverted Index.
    write_inverted_index(postings, inverted_path)

    # Store details about the Inverted Index.
    meta = {
        "source_forward": os.path.basename(forward_path),
        "forward_sha256": file_fingerprint(forward_path),
        "lexicon_sha256": file_fingerprint(lexicon_path),
        "num_docs": num_docs,
        "num_words": len(postings),
        "vocab_size": len(lexicon),
        "num_postings": num_postings,
        "inverted_size_bytes": os.path.getsize(inverted_path),
        "format": "JSONL"
    }

    # Save the metadata separately.
    write_json_safely(meta, meta_path)

    return meta


# ---------------- LOAD METADATA ----------------

def load_inverted_meta(path):
    """
    Load the saved Inverted Index metadata.
    """

    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ---------------- CHECK INVERTED INDEX ----------------

def inverted_index_is_current(
    forward_path,
    lexicon_path,
    inverted_path,
    meta_path
):
    """
    Check whether the saved Inverted Index is still up to date.
    """

    # Check that both files exist.
    if not (
        os.path.exists(inverted_path)
        and os.path.exists(meta_path)
    ):
        return False, "no saved inverted index"

    # Load the saved metadata.
    meta = load_inverted_meta(meta_path)

    # Check whether it was built from the same Forward Index.
    if meta.get("source_forward") != os.path.basename(forward_path):
        return False, "built from a different Forward Index"

    # Check whether the Forward Index has changed.
    if meta.get("forward_sha256") != file_fingerprint(forward_path):
        return False, "the Forward Index has changed"

    # Check whether the Lexicon has changed.
    if meta.get("lexicon_sha256") != file_fingerprint(lexicon_path):
        return False, "the Lexicon has changed"

    # Check whether the Inverted Index file size has changed.
    if meta.get("inverted_size_bytes") != os.path.getsize(inverted_path):
        return False, "the Inverted Index file has changed or is incomplete"

    return True, "up to date"


# ---------------- READ INVERTED INDEX ----------------

def iter_inverted_index(path):
    """
    Read the Inverted Index one word at a time.
    """

    with open(path, 'r', encoding='utf-8') as f:

        for line in f:

            line = line.strip()

            # Skip empty lines.
            if not line:
                continue

            # Convert each JSON line into a Python object.
            yield json.loads(line)


# ---------------- FIND POSTINGS ----------------

def find_postings(path, word_ids):
    """
    Find postings for the requested word IDs.
    """

    wanted = set(word_ids)  # Remove duplicate IDs
    found = {}              # Store matching postings

    # Return an empty dictionary if no IDs are given.
    if not wanted:
        return found

    max_word_id = max(wanted)  # Get the highest requested ID

    # Read the Inverted Index in word ID order.
    for word_id, flat in iter_inverted_index(path):

        # Save postings if this word is requested.
        if word_id in wanted:
            found[word_id] = flat

        # Stop when all requested words are found.
        if len(found) == len(wanted):
            break

        # Stop after passing the highest requested ID.
        if word_id > max_word_id:
            break

    return found