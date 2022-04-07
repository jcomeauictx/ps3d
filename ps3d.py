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
OUTPUT = type('Files', (), {'obj': None, 'mtl': None})()
DEVICE = {
    'PageSize': [0, 0],
    'LineWidth': 1,
    'RGBColor': [0, 0, 0],  # black by default
    'Path': [],
}
MM = 25.4 / 72  # 1/72" ~= .3mm
PS3D = {}  # words of the language

def convert(infile=sys.stdin, objfile='stdout.obj', mtlfile='stdout.mtl'):
    '''
    convert .ps3d file to .obj format
    '''
    if infile != sys.stdin:
        infile = open(infile)
    OUTPUT.obj = open(objfile, 'w')
    OUTPUT.mtl = open(mtlfile, 'w')
    print('mtlfile', os.path.basename(mtlfile), file=OUTPUT.obj)
    PS3D.update(ps3d())
    shebang = next(infile)
    if not shebang.startswith('%!ps3d'):
        if shebang.startswith('%!ps'):
            logging.warning('plain postscript (not ps3d) file!')
        else:
            raise ValueError('valid input should start with "%!ps3d"')
    for line in infile:
        process(line)
    infile.close()
    OUTPUT.obj.close()
    OUTPUT.mtl.close()

def process(line):
    '''
    tokenize and interpret line of ps3d code
    '''
    tokens = line.split()
    for token in tokens:
        line = line.lstrip()[len(token):]
        if token.startswith('%'):
            print('#' + token[1:] + line, file=OUTPUT.obj)
            break
        if token.startswith('/'):
            STACK.append(token[1:])  # store literal as string
            continue
        elif token.startswith('('):
            endstring = line.index(')')  # no nested () allowed in string!
            STACK.append(token[1:] + line[:endstring])
            process(line[endstring + 2:])  # skip ') '
            break
        if token in PS3D:
            PS3D[token]()
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
        path = DEVICE['Path']
        FACES.append([])
        for index in range(len(path) - 1):
            logging.debug('stroking between %s and %s',
                          path[index], path[index + 1])
            # convert units to mm when creating vertices
            FACES[-1].append((  # tuple, not list
                path[index][0] * MM,
                path[index][1] * MM,
                path[index][2] * MM
            ))

    def showpage():
        vertices = []
        for face in FACES:
            indices = [len(vertices) + 1 + i for i in range(len(face))]
            for vertex in face:
                print('v %f %f %f' % vertex, file=OUTPUT.obj)
            print('f', *indices, file=OUTPUT.obj)

    words = locals()
    words['='] = _print
    return words

if __name__ == '__main__':
    convert(*sys.argv[1:])
