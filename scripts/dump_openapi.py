#!/usr/bin/env python3
'''Write the OpenAPI description of the JSON API to openapi.json.

The file is committed so that a change to the API surface shows up as a
reviewable diff, and so the TypeScript client can be generated from a
known-good artefact rather than from a running server.

CI regenerates it and fails if the result differs from what is checked
in, which is what stops the generated frontend types silently rotting.

    ./scripts/dump_openapi.py            # write openapi.json
    ./scripts/dump_openapi.py --check    # exit 1 if it would change
'''
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app                      # noqa: E402
from app.api import spec                        # noqa: E402

DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'openapi.json')


def build_spec():
    app = create_app()
    with app.app_context():
        return spec.spec


def render(document):
    #  sort_keys so the committed file is stable across runs and the diff
    #  reflects real changes rather than dict ordering.
    return json.dumps(document, indent=2, sort_keys=True) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default=DEFAULT_PATH)
    parser.add_argument('--check', action='store_true',
                        help='exit non-zero if the file is out of date')
    args = parser.parse_args()

    rendered = render(build_spec())

    if args.check:
        if not os.path.exists(args.out):
            print('%s does not exist; run scripts/dump_openapi.py'
                  % args.out, file=sys.stderr)
            return 1
        current = open(args.out).read()
        if current != rendered:
            print('%s is out of date. Run scripts/dump_openapi.py and '
                  'commit the result.' % args.out, file=sys.stderr)
            return 1
        print('%s is up to date' % args.out)
        return 0

    with open(args.out, 'w') as handle:
        handle.write(rendered)
    paths = len(json.loads(rendered).get('paths', {}))
    print('wrote %s (%d paths)' % (args.out, paths))
    return 0


if __name__ == '__main__':
    sys.exit(main())
