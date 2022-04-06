#!/usr/bin/python3
'''
Prototype of a 3D extension of postscript

Produces .obj files for 3d printing
'''
import sys, logging  # pylint: disable=multiple-imports
from ast import literal_eval

logging.basicConfig(level=logging.DEBUG if __debug__ else logging.INFO)

STACK = []
VERTICES = []
FACES = []
DEVICE = {
    'PageSize': [0, 0],
    'LineWidth': 1,
    'RGBColor': [0, 0, 0],  # black by default
}

def convert(infile=sys.stdin, objfile='stdout.obj', mtlfile='stdout.mtl'):
    '''
    convert .ps3d file to .obj format
    '''
    if infile != sys.stdin:
        infile = open(infile)
    objfile = open(objfile, 'w')
    mtlfile = open(mtlfile, 'w')
    words = ps3d()
    shebang = next(infile)
    if not shebang.startswith('%!ps3d'):
        raise ValueError('valid input should start with "%!ps3d"')
    for line in infile:
        tokens = line.split()
        for token in tokens:
            line = line.lstrip()[len(token):]
            if token.startswith('%'):
                objfile.write('#' + token[1:] + line)
                break
            if token.startswith('/'):
                STACK.append(token[1:])  # store literal as string
                continue
            if token in words:
                words[token]()
            else:
                try:
                    STACK.append(literal_eval(token))
                except ValueError as bad:
                    raise ValueError('unknown value ' + token) from bad
            logging.debug('STACK: %s', STACK)
    infile.close()
    objfile.close()
    mtlfile.close()

def ps3d():
    '''
    words which define the ps3d language
    '''
    # pylint: disable=possibly-unused-variable
    def add():
        STACK.append(STACK.pop() + STACK.pop())

    def _print():
        logging.info('stdout: %s', STACK.pop())

    def moveto():
        VERTICES.append([STACK.pop(-2), STACK.pop(), 0])

    def rlineto():
        if VERTICES:
            currentpoint = VERTICES[-1]
            displacement = STACK.pop(-2), STACK.pop()
            VERTICES.append([currentpoint[0] + displacement[0],
                             currentpoint[1] + displacement[1],
                             currentpoint[2]])
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

    def stroke():
        pass  # no-op for now

    def showpage():
        pass  # no-op

    words = locals()
    words['='] = _print
    return words

if __name__ == '__main__':
    convert(*sys.argv[1:])
