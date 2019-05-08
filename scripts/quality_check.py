from collections import defaultdict
import sys

import argparse
import os

UD, NDT = 'ud', 'ndt'
NNO, NOB = 'nno', 'nob'
FILENAME, COUNT, RATIO = 'filename', 'count', 'ratio'


def main(language, file_type, sort_by, max_items, skip_items):
    current_dir = os.path.dirname(os.path.relpath(__file__))
    directory = os.path.join(current_dir, '..', file_type, language)
    if not os.path.isdir(directory):
        raise SystemExit('{} does not exist'.format(directory))
    strange = get_different_annotations(directory, file_type)
    print_skewed(directory, strange, file_type, sort_by, max_items, skip_items)


def get_different_annotations(directory, file_type):
    diffs = defaultdict(lambda: defaultdict(int))
    for filename in os.listdir(directory):
        with open(os.path.join(directory, filename)) as f:
            for line in f.readlines():
                if '\t' in line:
                    word = get_word(line)
                    ner = get_ner(line, file_type)
                    diffs[word][ner] = diffs[word][ner] + 1

    candidates = dict([(word, tag_dict) for word, tag_dict in diffs.items() if len(tag_dict) > 1 and 'O' in tag_dict])
    strange = dict([(k, v) for k, v in candidates.items() if ratio(v) > 0.5])

    return strange


def print_skewed(directory, strange, file_type, sort_by, max_items, skip_items):
    def key(filename, word):
        if sort_by == FILENAME:
            return filename
        else:
            return word

    items = defaultdict(list)
    paths = [os.path.join(directory, path) for path in os.listdir(directory)]
    for path in paths:
        with open(path) as f:
            sentence = []
            wrong_word = None
            for line in f.readlines():
                if '\t' in line:
                    word = get_word(line)
                    ner = get_ner(line, file_type)
                    if word in strange and ner == 'O':
                        wrong_word = word
                        sentence.append('**{}** {}'.format(word, dict(strange[word])))
                    else:
                        sentence.append(word)

                else:
                    if wrong_word:
                        items[key(path, wrong_word)].append((os.path.join(directory, path), ' '.join(sentence)))
                    wrong_word = None
                    sentence = []

    def sort_items(items):
        if sort_by == FILENAME:
            return sorted(items.items(), key=lambda x: x[0])
        elif sort_by == COUNT:
            return sorted(items.items(), key=lambda x: len([x[1]]), reverse=True)
        elif sort_by == RATIO:
            return sorted(items.items(), key=lambda x: ratio(strange[x[0]]), reverse=True)

    print_items = sort_items(items)
    if skip_items:
        print_items = [x for x in print_items if x[0] not in skip_items]
    padding = 5
    width_path = max([len(x) for x in paths]) + padding + padding + padding
    width_key = max([len(x[0]) for x in print_items]) + padding

    i = 0
    for key, lst in print_items:
        for path, sentence in lst:
            i += 1
            if i > max_items:
                break
            sys.stdout.write('{k:<{wk}} {p:<{wp}} {s}\n'.format(k=key, wk=width_key, p=path, wp=width_path, s=sentence))



def get_ner(line, file_type):
    if file_type == UD:
        return line.strip().split('\t')[9]
    else:
        return line.strip().split('\t')[9].split('=')[1]


def get_word(line):
    return line.split('\t')[1]


def ratio(d):
    o = d['O']
    ner = sum([v for k, v in d.items() if k != 'O'])
    return float(ner) / float(o + ner)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Simple script to quality check the NER annotations')
    parser.add_argument('language', choices=[NOB, NNO])
    parser.add_argument('--type', choices=[NDT, UD], default=NDT)
    parser.add_argument('--sort', choices=[FILENAME, COUNT, RATIO], default=RATIO)
    parser.add_argument('--n', type=int, default=0)
    parser.add_argument('--skip', nargs='+', required=False)
    args = parser.parse_args()

    main(args.language, args.type, args.sort, args.n, args.skip)

    try:
        sys.stdout.close()
    except:
        pass
    try:
        sys.stderr.close()
    except:
        pass
