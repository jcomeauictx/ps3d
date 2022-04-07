#!/usr/bin/python3
'''
Prototype of a 3D extension of postscript

Produces .obj files for 3d printing
'''
import sys, os, logging  # pylint: disable=multiple-imports
from ast import literal_eval
from copy import deepcopy

logging.basicConfig(level=logging.DEBUG if __debug__ else logging.INFO)

STACK = []
GSTACK = []  # graphic state stack
FACES = []
DEVICE = {
    'PageSize': [0, 0],
    'LineWidth': 1,
    'RGBColor': [0, 0, 0],  # black by default
    'Path': [],
}

def convert(infile=sys.stdin, objfile='stdout.obj', mtlfile='stdout.mtl'):
    '''
    convert .ps3d file to .obj format
    '''
    if infile != sys.stdin:
        infile = open(infile)
    objfile = open(objfile, 'w')
    mtlfile = open(mtlfile, 'w')
    print('mtlfile', os.path.basename(mtlfile.name), file=objfile)
    words = ps3d()
    shebang = next(infile)
    if not shebang.startswith('%!ps3d'):
        if shebang.startswith('%!ps'):
            logging.warning('plain postscript (not ps3d) file!')
        else:
            raise ValueError('valid input should start with "%!ps3d"')
    for line in infile:
        process(line, words, objfile, mtlfile)
    infile.close()
    objfile.close()
    mtlfile.close()

def process(line, words, objfile, mtlfile):
    '''
    tokenize and interpret line of ps3d code
    '''
    tokens = line.split()
    for token in tokens:
        line = line.lstrip()[len(token):]
        if token.startswith('%'):
            objfile.write('#' + token[1:] + line)
            break
        if token.startswith('/'):
            STACK.append(token[1:])  # store literal as string
            continue
        elif token.startswith('('):
            endstring = line.index(')')  # no nested () in string!
            STACK.append(token[1:] + line[:endstring])
            process(line[endstring + 2:], words, objfile, mtlfile)  # skip ') '
            break
        if token in words:
            words[token]()
        else:
            try:
                STACK.append(literal_eval(token))
            except ValueError as bad:
                raise ValueError('unknown value ' + token) from bad
        logging.debug('STACK: %s', STACK)

def ps3d():
    '''
    words which define the ps3d language
    '''
    # pylint: disable=possibly-unused-variable, too-many-locals
    def add():
        STACK.append(STACK.pop() + STACK.pop())

    def _print():
        logging.info('stdout: %s', STACK.pop())

    def moveto():
        DEVICE['Path'].append([STACK.pop(-2), STACK.pop(), 0, 'moveto'])

    def rlineto():
        if DEVICE['Path']:
            currentpoint = DEVICE['Path'][-1]
            displacement = STACK.pop(-2), STACK.pop()
            DEVICE['Path'].append([
                currentpoint[0] + displacement[0],
                currentpoint[1] + displacement[1],
                currentpoint[2],
                'lineto'
            ])
        else:
            raise ValueError('no current point')

    def currentpagedevice():
        STACK.append(DEVICE)

    def get():
        index = STACK.pop()
        STACK.append(STACK.pop().__getitem__(index))

    def div():
        divisor = STACK.pop()
        STACK.append(STACK.pop() / divisor)

    def dup():
        STACK.append(STACK[-1])

    def exch():
        STACK[-2], STACK[-1] = STACK[-1], STACK[-2]

    def setrgbcolor():
        DEVICE['RGBColor'] = [STACK.pop(-3), STACK.pop(-2), STACK.pop()]
        logging.debug('color now: %s', DEVICE['RGBColor'])

    def setgray():
        STACK.extend([STACK.pop()] * 3)
        setrgbcolor()

    def gsave():
        GSTACK.append(deepcopy(DEVICE))

    def grestore():
        DEVICE.update(GSTACK.pop())

    def stroke():
        pass  # no-op for now

    def showpage():
        pass  # no-op

    words = locals()
    words['='] = _print
    return words

if __name__ == '__main__':
    convert(*sys.argv[1:])
