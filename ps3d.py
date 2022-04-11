#!/usr/bin/python3
'''
Prototype of a 3D extension of postscript

Produces .obj files for 3d printing

Some notes:
    Z axis points towards viewer, -Z points away; what gets printed last
    is "top".

    Vertices can be created in any order, *but* faces must enumerate them
    in counterclockwise order; otherwise they will appear backwards (dark side
    to viewer) or broken (if neither CW nor CCW).
'''
import sys, os, math, logging  # pylint: disable=multiple-imports
from ast import literal_eval
from copy import deepcopy
from collections import namedtuple
from datetime import datetime

logging.basicConfig(level=logging.DEBUG if __debug__ else logging.INFO)

STACK = []
GSTACK = []  # graphic state stack
VERTICES = []
FACES = []
OUTPUT = type('Files', (), {'obj': None, 'mtl': None})()
BLACK = [0, 0, 0]
WHITE = [1, 1, 1]
COLORS = [WHITE]
DEVICE = {
    'PageSize': [0, 0],
    'LineWidth': 1,
    'RGBColor': WHITE,  # black shows as white by default
    'Path': [],
}
MM = 25.4 / 72  # 1/72" ~= .35mm; in case we want to convert
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
# check equality only for x, y, z
Triplet.__eq__ = lambda self, other: self[:3] == other[:3]

def convert(infile=sys.stdin, objfile='stdout.obj', mtlfile='stdout.mtl'):
    '''
    convert .ps3d file to .obj format
    '''
    if infile != sys.stdin:
        infile = open(infile)
    OUTPUT.obj = open(objfile, 'w')
    OUTPUT.mtl = open(mtlfile, 'w')
    print(
        '# created %s from %s by %s' % (
            datetime.now(), infile.name, sys.argv[0]
        ), file=OUTPUT.obj
    )
    print('# units are 1/72 inch, same as PostScript', file=OUTPUT.obj)
    print("# that's .013888 inches or .352777 mm", file=OUTPUT.obj)
    print('mtllib', os.path.basename(mtlfile), file=OUTPUT.obj)
    print('newmtl mtl0', file=OUTPUT.mtl)
    print('Kd 1 1 1', file=OUTPUT.mtl)  # black in postscript, white in 3D
    print('g mtl0', file=OUTPUT.obj)
    print('usemtl mtl0', file=OUTPUT.obj)
    PS3D.update(ps3d())
    shebang = next(infile)
    if not shebang.startswith('%!ps3d'):
        if shebang.startswith('%!ps'):
            logging.warning('plain postscript (not ps3d) file!')
        else:
            raise ValueError('Valid input should start with "%!ps3d"')
    for line in infile:
        print('# ps code:', line.rstrip(), file=OUTPUT.obj)
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
            print('#' + token[1:] + line.rstrip(), file=OUTPUT.obj)
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
                raise ValueError('Unknown value ' + token) from bad
        logging.debug('STACK: %s', STACK)

def atan2(point0, point1):
    '''
    angle in positive degrees between two points in the xy plane
    '''
    atan = math.degrees(math.atan2(
        point1.y - point0.y, point1.x - point0.x
    ))
    # make sure it's positive
    return (360 + atan) % 360

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

def get_vertex(point):
    '''
    return index into VERTICES for given point

    must be 1-based to use in face ('f') statement
    '''
    try:
        return VERTICES.index(point)
    except ValueError:
        VERTICES.append(point)
        return len(VERTICES) - 1

def outer_join(index, segments):
    '''
    make a seamless join where two segments meet
    '''
    get_x = lambda top, index: VERTICES[top[index] - 1].x
    get_y = lambda top, index: VERTICES[top[index] - 1].y
    logging.debug('outer_join: segments: %s', segments)
    outer_lines = [
        [Triplet(get_x(top, 1), get_y(top, 1)),
         Triplet(get_x(top, 0), get_y(top, 0))]
        for top in (segments[index]['top'], segments[index - 1]['top'])
    ]
    logging.debug('joining outer lines: %s', outer_lines)
    formulas = [line_formula(*line) for line in outer_lines]
    logging.debug('formulas: %s', formulas)

def line_formula(start, end):
    '''
    calculate formula `y = mx + c` for line from two points

    where m = delta y divided by delta x. if delta x is zero, it's a vertical
    line, so simply return the formula `x = c`.
    '''
    delta_y = end.y - start.y
    delta_x = end.x - start.x
    if delta_x == 0:
        formula = {'x': start.x}
    else:
        formula = {'m': delta_y / delta_x}
        # now calculate c using either point
        formula['c'] = start.y - formula['m'] * start.x
    logging.debug('delta_x: %s, delta_y: %s, formula: %s',
                  delta_x, delta_y, formula)
    return formula

def ps3d():
    '''
    words which define the ps3d language
    '''
    # pylint: disable=possibly-unused-variable
    # pylint: disable=too-many-statements, too-many-locals  # can't be helped
    def add():
        STACK.append(STACK.pop() + STACK.pop())

    def _print():
        print('# stdout:', STACK.pop(), file=OUTPUT.obj)

    def moveto():
        DEVICE['Path'] = []  # clear current path
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

    def setrgbcolor(useblack=True):
        '''
        use white by default when called via `0 setgray`

        easier to see problems with white items in MeshLab than with black
        '''
        color = [STACK.pop(-3), STACK.pop(-2), STACK.pop()]
        if color == BLACK and not useblack:
            color = WHITE
        if color != DEVICE['RGBColor']:
            DEVICE['RGBColor'] = color
            logging.debug('color now: %s', DEVICE['RGBColor'])
            if color in COLORS:
                logging.debug('color %s already in COLORS: %s', color, COLORS)
                group = 'mtl%d' % COLORS.index(color)
            else:
                group = 'mtl%d' % len(COLORS)
                COLORS.append(color)
                print('', file=OUTPUT.mtl)
                print('newmtl', group, file=OUTPUT.mtl)
                print('Kd', *color, file=OUTPUT.mtl)
            print('g', group, file=OUTPUT.obj)
            print('usemtl', group, file=OUTPUT.obj)
        else:
            logging.info('color was already %s', color)

    def setgray(useblack=False):
        if STACK[-1] == 0:
            logging.warning('using white not black, see .obj file for details')
            print('# use 0 0 0 setrgbcolor for black', file=OUTPUT.obj)
        STACK.extend([STACK.pop()] * 3)
        setrgbcolor(useblack)

    def gsave():
        GSTACK.append(deepcopy(DEVICE))

    def grestore():
        DEVICE.update(GSTACK.pop())

    def setlinewidth():
        DEVICE['LineWidth'] = STACK.pop()

    def stroke():
        '''
        draw current path as a single, thin, ridge

        using line width as thickness for now; it should probably be at least
        3 PostScript units, about 1mm, to be rendered properly by 3D printer
        '''
        path = DEVICE['Path']
        linewidth = DEVICE['LineWidth']
        if linewidth * MM < 1:
            raise ValueError('Width less than a millimeter not likely to work')
        halfwidth = linewidth / 2
        logging.debug('half line width: %s mm', halfwidth)
        segments = []
        # we need to make 3 loops, building boxes around the path segments;
        # the outmost loop iterates over the segments;
        # the next inner loop creates the faces: top, bottom, left, right;
        # the innermost loop creates the vertices.
        # vertices can and should be reused
        # should add a face to each end of the resulting path

        def get_faces(start, end):
            '''
            think of the segment as a ship going from start to end

            you're the captain, steering, and "top left" is the port foredeck.
            the vertices are numbered counterclockwise: port aft, starboard
            aft, starboard fore. those are the last to be printed, since the
            Z axis is "top". vertices 5 through 8 are in the corresponding
            places on the hull below. while enumerating the other faces,
            imagine the boat is roughly cubic, the helm always remains upright,
            but the rest of the boat rolls or pitches over to another face.
            so when, for example, the hull and deck are swapped, the
            numbering becomes 8, 7, 6, 5.
            '''
            theta = atan2(start, end)
            logging.debug('stroking between %s and %s, angle %s degrees',
                          path[index], path[index + 1], theta)
            adjustment = halfwidth
            sin_offset = sin(theta) * adjustment
            cos_offset = cos(theta) * adjustment
            vertices = [get_vertex(point) for point in (
                end + Triplet(-sin_offset, cos_offset, linewidth),
                start + Triplet(-sin_offset, cos_offset, linewidth),
                start + Triplet(sin_offset, -cos_offset, linewidth),
                end + Triplet(sin_offset, -cos_offset, linewidth),
                end + Triplet(-sin_offset, cos_offset),
                start + Triplet(-sin_offset, cos_offset),
                start + Triplet(sin_offset, -cos_offset),
                end + Triplet(sin_offset, -cos_offset)
            )]
            logging.debug('vertices: %s', vertices)
            faces = {
                'top': list(vertices[i - 1] + 1 for i in [1, 2, 3, 4]),
                'bottom': list(vertices[i - 1] + 1 for i in [8, 7, 6, 5]),
                'left': list(vertices[i - 1] + 1 for i in [5, 6, 2, 1]),
                'right': list(vertices[i - 1] + 1 for i in [4, 3, 7, 8]),
                'start': list(vertices[i - 1] + 1 for i in [2, 6, 7, 3]),
                'end': list(vertices[i - 1] + 1 for i in [5, 1, 4, 8]),
            }
            return faces

        for index in range(len(path) - 1):
            segments.append(get_faces(path[index], path[index + 1]))
        FACES.append(segments[0]['start'])  # near end cap
        for segment in segments:
            FACES.extend([
                segment[k] for k in ('top', 'left', 'bottom', 'right')
            ])
        FACES.append(segments[-1]['end'])  # far end cap

        # now join the segments seamlessly

        for index in range(1, len(segments)):
            outer_join(index, segments)

        DEVICE['Path'] = []  # clear path after stroke

    def showpage():
        for vertex in VERTICES:
            print('v %f %f %f' % vertex[:3], file=OUTPUT.obj)
        for face in FACES:
            print('f', *face, file=OUTPUT.obj)

    words = locals()
    words['='] = _print
    return words

if __name__ == '__main__':
    convert(*sys.argv[1:])
