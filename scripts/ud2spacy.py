import argparse
import logging
import os
import re

logging.basicConfig(level=logging.INFO)

NNO, NOB = 'nno', 'nob'


def get_ud_dir(language):
    current_dir = os.path.dirname(os.path.relpath(__file__))
    return os.path.join(current_dir, '..', 'ud', language)


name_re = re.compile('.*?name=([\w\-]+).*?')


def fix_line(l):
    columns = l.split('\t')
    m = name_re.search(columns[-1])
    if m:
        columns[-1] = m.group(1)
        return '\t'.join(columns) + '\n'
    else:
        return l


def main(language, outputdir):
    ud_dir = get_ud_dir(language)
    if not os.path.isdir(outputdir):
        logging.info('Creating directory: {}'.format(outputdir))
        os.makedirs(outputdir)
    for filename in os.listdir(ud_dir):
        with open(os.path.join(outputdir, filename), 'w') as outputfile:
            logging.info('Writing spacy file to {}'.format(outputfile.name))
            with open(os.path.join(ud_dir, filename)) as inputfile:
                for line in inputfile:
                    outputfile.write(fix_line(line))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fix UD name annotations for Spacy')
    parser.add_argument('language', choices=[NOB, NNO])
    parser.add_argument('--outputdir', default='output')
    args = parser.parse_args()

    main(args.language, args.outputdir)
