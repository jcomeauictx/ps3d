#!/usr/bin/python3
'''
Prototype of a 3D extension of postscript

Produces .obj files for 3d printing

Some notes:
    Z axis points towards viewer, -Z points away.
    Vertices can be created in any order, *but* faces must enumerate them
    in counterclockwise order; otherwise they will appear backwards (dark side
    to viewer) or broken (if neither CW nor CCW).
'''
import sys, os, math, logging  # pylint: disable=multiple-imports
from ast import literal_eval
from copy import deepcopy
from collections import namedtuple

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
# Triplet: x, y, z values that can be used in arithmetic operations with scalars
Triplet = namedtuple(
    'Triplet',
    ('x', 'y', 'z', 'type'),
    defaults=(0, 0, 0, None)
)
Triplet.__add__ = lambda self, other: Triplet(
    self.x + other.x, self.y + other.y, self.z + other.z, other.type
) if hasattr(other, 'x') else Triplet(
    self.x + other, self.y + other, self.z + other, self.type
)
Triplet.__mul__ = lambda self, other: Triplet(  # only scalar
    self.x * other, self.y * other, self.z * other, self.type
)

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

def atan2(point0, point1):
    '''
    angle in degrees between two points in the xy plane
    '''
    return math.degrees(math.atan2(
        point1.y - point0.y, point1.x - point0.x
    ))

def sin(theta):
    '''
    y displacement for given angle theta (degrees)
    '''
    return math.sin(math.radians(theta))

def cos(theta):
    '''
    x displacement for given angle theta (degrees)
    '''
    return math.cos(math.radians(theta))

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
        DEVICE['Path'].append(Triplet(
            STACK.pop(-2), STACK.pop(), 0, 'moveto'
        ))

    def rlineto():
        if DEVICE['Path']:
            currentpoint = DEVICE['Path'][-1]
            displacement = Triplet(STACK.pop(-2), STACK.pop(), 0, 'lineto')
            logging.debug('adding %s and %s and appending to %s',
                          currentpoint, displacement, DEVICE['Path'])
            DEVICE['Path'].append(currentpoint + displacement)
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
        '''
        draw current path as a single, thin, ridge

        using DEVICE['LineWidth'] as thickness, may need to revisit that
        '''
        path = DEVICE['Path']
        halfwidth = DEVICE['LineWidth'] / 2
        logging.debug('half line width: %s', halfwidth)
        FACES.append([])
        # we need to make 3 loops, building boxes around the path segments;
        # the outmost loop iterates over the segments;
        # the next inner loop creates the faces: front, top, rear, bottom;
        # the innermost loop creates the vertices.
        # vertices can and should be reused
        for index in range(len(path) - 1):
            theta = atan2(path[index], path[index + 1])
            logging.debug('stroking between %s and %s, angle %s degrees',
                          path[index], path[index + 1], theta)
            # convert units to mm when creating vertices

    def showpage():
        vertices = []
        for face in FACES:
            indices = [len(vertices) + 1 + i for i in range(len(face))]
            for vertex in face:
                print('v %f %f %f' % vertex[:3], file=OUTPUT.obj)
                vertices.append(vertex)
            print('f', *indices, file=OUTPUT.obj)

    words = locals()
    words['='] = _print
    return words

if __name__ == '__main__':
    convert(*sys.argv[1:])
