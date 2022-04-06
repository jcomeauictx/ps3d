#!/usr/bin/python3
'''
Prototype of a 3D extension of postscript

Produces .obj files for 3d printing
'''
import sys, logging  # pylint: disable=multiple-imports
from ast import literal_eval

logging.basicConfig(level=logging.DEBUG if __debug__ else logging.INFO)

STACK = []

def convert(infile=sys.stdin, outfile=sys.stdout):
    '''
    convert .ps3d file to .obj format
    '''
    if infile != sys.stdin:
        infile = open(infile)
    if outfile != sys.stdout:
        outfile = open(outfile, 'w')
    words = ps3d()
    shebang = next(infile)
    if not shebang.startswith('%!ps3d'):
        raise ValueError('valid input should start with "%!ps3d"')
    for line in infile:
        tokens = line.split()
        for token in tokens:
            line = line.lstrip()[len(token):]
            if token.startswith('%'):
                outfile.write('#' + token[1:] + line)
                break
            if token in words:
                words[token]()
            else:
                try:
                    STACK.append(literal_eval(token))
                except ValueError as bad:
                    raise ValueError('unknown value ' + token) from bad
            logging.debug('STACK: %s', STACK)
    infile.close()
    outfile.close()

def ps3d():
    '''
    words which define the ps3d language
    '''
    # pylint: disable=possibly-unused-variable
    def add():
        STACK.append(STACK.pop() + STACK.pop())
    return locals()

if __name__ == '__main__':
    convert(*sys.argv[1:])
