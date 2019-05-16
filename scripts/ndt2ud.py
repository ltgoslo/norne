# coding=utf-8
import codecs
import logging
import re
from collections import defaultdict
import io

import argparse
import os
from git import Repo

logging.basicConfig(level=logging.INFO)

NNO, NOB = 'nno', 'nob'

URLS = {NNO: 'https://github.com/UniversalDependencies/UD_Norwegian-Nynorsk',
        NOB: 'https://github.com/UniversalDependencies/UD_Norwegian-Bokmaal'}


def main(language, outputdir):
    ndt_data = read_ndt(language)
    download_ud_if_necessary(language)
    ud_data = read_ud(language)
    result = merge(ndt_data, ud_data)
    write_result(result, outputdir)
    assert_equal(result.keys(), get_git_dir(language), outputdir)


def merge(ndt_data, ud_data):
    result = {}
    input_files = ud_data.keys()

    for ud_file in input_files:
        merged = []
        while len(ud_data[ud_file]):
            ndt_file = find_next_ndt_file(ud_data[ud_file], ndt_data)
            if ndt_file is None:
                merged.extend(ud_data[ud_file])
                ud_data[ud_file] = []
            else:
                logging.info('Adding to {}: {}'.format(ud_file, ndt_file))
                merged, new_ud = merge_data(ud_data[ud_file], ndt_data[ndt_file], merged)
                ud_data[ud_file] = new_ud
                del ndt_data[ndt_file]

        result[ud_file] = merged
    return result


def write_result(result, outputdir):
    if not os.path.isdir(outputdir):
        logging.info('Creating directory: {}'.format(outputdir))
        os.makedirs(outputdir)
    for key in result:
        path = os.path.join(outputdir, key)
        logging.info('Writing results to {}'.format(path))
        with open(path, "w") as f:
            lines = ['\t'.join(line) + '\n' for line in result[key]]
            f.writelines(lines)


def assert_equal(filenames, inputdir, outputdir):
    def read_lines(path):
        with open(path) as f:
            return [x.strip() for x in f.readlines()]

    name_re = re.compile('\|?name=(O|[BI]-\w+)')

    def remove_name(i, o):
        if i.split('\t')[-1] == '_':
            return name_re.sub('_', o)
        else:
            return name_re.sub('', o)

    for fn in filenames:
        input_path = os.path.join(inputdir, fn)
        output_path = os.path.join(outputdir, fn)

        input_lines = read_lines(input_path)
        output_lines = read_lines(output_path)

        for idx, (inp, outp) in enumerate(zip(input_lines, output_lines)):
            try:
                outp_name_removed = remove_name(inp, outp)
                assert inp == outp_name_removed
            except AssertionError as e:
                logging.error("Lines are not equal in files, line {}".format(idx))
                logging.error('Input file  (length={}):  {}'.format(len(input_lines), input_path))
                logging.error('Output file (length={}):  {}'.format(len(output_lines), output_path))
                logging.error('INPUT:                 {}'.format(inp))
                logging.error('OUTPUT (name removed): {}'.format(outp_name_removed))
                logging.error('OUTPUT:                {}'.format(outp))
                exit()
        logging.info("File looks correct: {}".format(output_path))


def find_next_ndt_file(ud_lines, ndt_data):
    ud_words = [x[1] for x in ud_lines if len(x) > 5]
    best = 1.0
    best_ndt = None
    for ndt in sorted(ndt_data.keys()):
        ndt_words = [x[0] for x in ndt_data[ndt] if len(x) == 2]
        ud = ud_words[:len(ndt_words)]
        correct = +1
        idx = 0
        for word in ndt_words:
            if idx < len(ud) and word == ud[idx]:
                correct += 1
                idx += 1
        if correct > 1:
            logging.debug('{} (overlap={}):'.format(ndt, correct))
        if correct > best:
            best = correct
            best_ndt = ndt
            logging.debug('New best (overlap={}): {}'.format(best, best_ndt))

    logging.debug('Best next file (overlap={}): {}'.format(best, best_ndt))
    return best_ndt


def line_match(ndt_line, ud_line):
    ndt = ndt_line[0]
    ud = ud_line[1]

    edge_cases = {
        'Sjå': 'SJÅ',
        'må': 'MÅ',
        'Tequila-dagbøkene': 'TEQUILA-DAGBØKENE',
        'Ndranghetaen': '\'Ndranghetaen',
        'Lærdals-ordførar': 'Lærdals-ordføraren',
        'stortinget': 'Stortinget',
        'Nedleggjing': 'NEDLEGGJING',
        'fN-landenes': 'FN-landenes',
        'norge': 'Norge',
        'du': 'Du',
        'å': 'Å',
        'at': 'ved',
        'nissespik': 'Nissespik',
        '-sosialtenestene': 'sosialtenestene',
        '-nattestid': 'nattestid',
        '-Aust-Telemark': 'Aust-Telemark',
        'PST': 'pst',
        'vi': 'oss',
        '-turistsenteret': 'turistsenteret',
    }

    if ndt == ud:
        return True
    elif ndt in {'«', '»', '”', '“', '"'} and ud in {"'", '"', '”', '“', '»'}:
        return True
    elif ndt == ud + '.':
        return True
    elif ndt in edge_cases and edge_cases[ndt] == ud:
        return True

    if ndt != '|' and ndt != '.':
        logging.error('NDT ne UD:\n\'{}\': \'{}\','.format(ndt, ud))
    return False


def valid_ud(line):
    if len(line) == 0:
        return True
    if len(line) == 1 and line[0] == '':
        return True
    if line[0].startswith('#'):
        return True
    return False


def skip_ndt(line):
    if len(line) == 0:
        return True
    return False


def skip_ndt_2(ud_line, ndt_line):
    edge_cases = {'«': '\'Ndranghetaen'}

    if len(ud_line) > 5:
        ud = ud_line[1]
        ndt = ndt_line[0]
        return ndt in edge_cases and edge_cases[ndt] == ud

    return False


def retry_ndt(line):
    if line[0] in {'|', '.'}:
        return True
    return False


def merge_data(ud, ndt, merged):
    ud_i = 0
    ndt_i = 0
    sentid = None

    merged_count = 0
    while ndt_i < len(ndt):
        ndt_line = ndt[ndt_i]
        ud_line = ud[ud_i]
        if '# sent_id' in ' '.join(ud_line):
            sentid = ' '.join(ud_line)
            logging.debug(sentid)
        if skip_ndt(ndt_line):
            ndt_i += 1
        elif skip_ndt_2(ud_line, ndt_line):
            ndt_i += 1
        elif valid_ud(ud_line):
            merged.append(ud_line)
            merged_count += 1
            ud_i += 1
        elif line_match(ndt_line, ud_line):
            if ud_line[-1] == '_':
                ud_line[-1] = 'name={}'.format(ndt_line[1])
            else:
                ud_line[-1] += '|name={}'.format(ndt_line[1])
            merged.append(ud_line)
            merged_count += 1
            ud_i += 1
            ndt_i += 1
        elif retry_ndt(ndt_line):
            ndt_i += 1
        else:
            # Log some info to debug what happened
            logging.error('NDT {}'.format(ndt_i))
            logging.error(' '.join([x[0] for x in ndt[ndt_i:ndt_i + 100]]))
            logging.error('UD {} sentid={}'.format(ud_i, sentid))
            logging.error(' '.join([x[1] for x in ud[ud_i:ud_i + 100] if len(x) > 5]))
            logging.error('MERGED')
            logging.error(' '.join([x[1] for x in merged[-10:] if len(x) > 5]))
            exit()
    return merged, ud[merged_count:]


def download_ud_if_necessary(language):
    git_dir = get_git_dir(language)
    if not os.path.exists(git_dir):
        os.makedirs(git_dir)
        Repo.clone_from(URLS[language], git_dir)


def get_ndt_dir(language):
    current_dir = os.path.dirname(os.path.relpath(__file__))
    return os.path.join(current_dir, '..', 'ndt', language)


def get_git_dir(language):
    return os.path.join('git', language)


def read_ndt(language):
    directory = get_ndt_dir(language)
    data = defaultdict(list)
    for filename in os.listdir(directory):
        with io.open(os.path.join(directory, filename), encoding='utf-8') as f:
            for line in f.readlines():
                line = line.encode('utf-8').strip()
                if '\t' in line:
                    word = get_word(line)
                    ner = get_ner(line)
                    data[filename].append((word, ner))
    return data


def read_ud(language):
    data = {}
    directory = get_git_dir(language)
    for filename in os.listdir(directory):
        if filename.endswith('.conllu'):
            with io.open(os.path.join(directory, filename), encoding='utf-8') as f:
                data[filename] = [x.encode('utf-8').strip().split('\t') for x in f.readlines()]
    return data


def get_ner(line):
    return line.strip().split('\t')[9].split('=')[1]


def get_word(line):
    return line.split('\t')[1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create NER annotations for UD')
    parser.add_argument('language', choices=[NOB, NNO])
    parser.add_argument('--outputdir', default='output')
    args = parser.parse_args()

    main(args.language, args.outputdir)
