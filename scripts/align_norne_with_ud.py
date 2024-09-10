import os
import argparse
from typing import List
from tqdm import tqdm
from enum import Enum
from dataclasses import dataclass
from conllu import TokenList, parse


class Language(Enum):
    BOKMAAL = "bokmaal"
    NYNORSK = "nynorsk"


@dataclass
class Paths:
    train: str
    test: str
    dev: str


def get_paths(path: str) -> Paths:
    """
    Retrieves the paths to the train, test, and dev CoNLL-U format files for a corpus.

    Args:
        path (str): The path to the corpus directory.

    Returns:
        Paths: A Paths object containing the paths to the train, test, and dev files.
    """
    files = [os.path.join(path, file) for file in os.listdir(path)
             if file.endswith(".conllu")]

    return Paths(
        train=[f for f in files if "train" in f][0],
        test=[f for f in files if "test" in f][0],
        dev=[f for f in files if "dev" in f][0],
    )

def align_norne(norne: str, ud: str, output: str) -> None:
    """
    Aligns the NorNE and UD Norwegian corpora and writes the aligned data to
    CoNLL-U format files.

    Args:
        norne (str): The path to the NorNE corpus directory.
        ud (str): The path to the UD Norwegian corpus directory.
        output (str): The path to the output directory.

    Returns:
        None
    """
    os.makedirs(output, exist_ok=True)

    for lang in Language:
        norne_id = "nob" if lang == Language.BOKMAAL else "nno"
        ud_id = f"UD_Norwegian-{lang.value.capitalize()}"

        NORNE = get_paths(os.path.join(norne, norne_id))
        UD = get_paths(os.path.join(ud, ud_id))

        for split in ["train", "test", "dev"]:
            norne_path = getattr(NORNE, split)
            ud_path = getattr(UD, split)
            print(split)
            print(norne_path, ud_path)

            with open(ud_path, "r", encoding="utf-8") as ud_f, open(norne_path, "r", encoding="utf-8") as entity_f:
                ud_data = parse(ud_f.read())
                entity_data = parse(entity_f.read())

            out_filename = f"no_{lang.value}-ud-{split}.conllu"
            out = os.path.join(output, norne_id, out_filename)
            os.makedirs(os.path.dirname(out), exist_ok=True)

            aligned_data = align_sentences(ud_data, entity_data)

            with open(out, "w", encoding="utf-8", newline="\n") as f:
                for sent in aligned_data:
                    f.write(sent.serialize())


def align_sentences(ud_data: List[TokenList], entity_data: List[TokenList]) -> List[TokenList]:
    """
    Aligns the sentences in the UD Norwegian and NorNE corpora.

    Args:
        ud_data (List[TokenList]): The UD Norwegian corpus data.
        entity_data (List[TokenList]): The NorNE corpus data.

    Returns:
        List[TokenList]: The aligned data.
    """
    aligned_data = []

    # some sentences are split across two sentences in the NorNE data
    # keep track of this index
    entity_extra_idx_iterator = 0

    for i in tqdm(range(len(ud_data))):
        ud_sent = ud_data[i]
        entity_sent = entity_data[i + entity_extra_idx_iterator]

        valid_idx = i + entity_extra_idx_iterator + 1 < len(entity_data)
        if valid_idx:
            entity_sent_nxt = entity_data[i + entity_extra_idx_iterator + 1]
            next_entity_text = entity_sent_nxt.metadata["text"]

        meta = ud_sent.metadata  # we will modify the entire object, so save it
        ud_text = ud_sent.metadata["text"]
        entity_text = entity_sent.metadata["text"]

        if ud_text == entity_text:
            aligned = merge_sentences(ud_sent, entity_sent)
            ud_data[i] = aligned
        elif ud_text == entity_text + next_entity_text and valid_idx:
            # try to match the UD sent with the next NorNE sent
            # such that UD1 = NorNE1 + NorNE2
            entity_tokens = [t for t in entity_sent]
            entity_tokens_nxt = [t for t in entity_sent_nxt]
            merged = TokenList(entity_tokens + entity_tokens_nxt)
            aligned = merge_sentences(ud_sent, merged)
            ud_data[i] = aligned
            entity_extra_idx_iterator += 1
        elif ud_text == entity_text[1:]:
            # we may get:
            # En kampanje for "etnisk renskning" starter med at én nabo vender seg mot en annen.
            # "En kampanje for "etnisk renskning" starter med at én nabo vender seg mot en annen.
            # that is, the norne sentence has an unnecessary token at the beginning. Ignore it!
            entity_tokens = [t for t in entity_sent]
            merged = TokenList(entity_tokens[1:])
            aligned = merge_sentences(ud_sent, merged)
            ud_data[i] = aligned
        else:
            print(
                f"Mismatched sentences on line {ud_sent.metadata['sent_id']}")
            print(ud_sent.metadata["text"])
            print(entity_sent.metadata["text"])
            print("_"*40)

        ud_data[i].metadata = meta
        aligned_data.append(ud_data[i])

    return aligned_data

def merge_sentences(ud: TokenList, entity: TokenList) -> TokenList:
    """
    Merges the UD Norwegian and NorNE corpus data for a single sentence.

    Args:
        ud (TokenList): The UD Norwegian corpus data for the sentence.
        entity (TokenList): The NorNE corpus data for the sentence.

    Returns:
        TokenList: The merged data.
    """
    ud_toks = [t for t in ud]
    entity_toks = [t for t in entity]
    for j, ud_tok in enumerate(ud_toks):
        ud_misc = ud_tok["misc"] or {}
        entity_misc = entity_toks[j]["misc"] or {}
        entity_misc = {k: v for k, v in entity_misc.items() if k == "name"}

        ud_misc.update(entity_misc)
        ud_tok["misc"] = ud_misc

    return TokenList(ud_toks)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--norne", "-n", type=str, required=False,
                        help="Source for NorNE data", default="ud/")
    parser.add_argument("--ud", "-u", type=str, required=True,
                        help="Source for UD data")
    parser.add_argument("--output", "-o", type=str, required=False,
                        help="Merged files location", default="ud_aligned/")
    args = parser.parse_args()

    if not os.path.isfile("requirements.txt"):
        print(f"""
        {'*' * 46}
        Please run this script from the main folder
        e.g. `python scripts/align_norne.py *params*`
        {'*' * 46}
        """)
        exit()

    align_norne(args.norne, args.ud, args.output)
