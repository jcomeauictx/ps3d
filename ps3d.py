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
VERTEX = []
FACE = []
OUTPUT = type('Files', (), {'obj': None, 'mtl': None})()
BLACK = [0, 0, 0]
WHITE = [1, 1, 1]
COLOR = [WHITE]
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
# Vertex is a triplet that returns its index into VERTEX
Vertex = type('Vertex', (Triplet,), {})
Vertex.index = property(
    lambda v: VERTEX.index(v)  # pylint: disable=unnecessary-lambda
)

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
    return index into VERTEX for given point

    must be 1-based to use in face ('f') statement
    '''
    try:
        return VERTEX.index(point)
    except ValueError:
        VERTEX.append(point)
        return len(VERTEX) - 1

def join(index, segments):
    '''
    make a seamless join where two segments meet

    this is a bit complicated. remember:
    `segments` is a list of line segments forming a path: [SEG, SEG, ...]
    each SEG is a dict: {'top': [V, V, V, V], 'bottom': [V, V, V, V], ...}
    each V is a 1-based index into VERTEX
    VERTEX[V - 1] is a Triplet of (x, y, z)
    first, we want to determine the intersection of the outer lines of
    each segment, then modify those vertices to the intersection point.
    then do the same with the inner lines.
    if the angle is less than 180 degrees, 'outer' will be 'port' side in
    the "ship" analogy, otherwise 'starboard'
    '''
    outer_leading = [  # listed stern to bow for each grouping
        Vertex(*VERTEX[segments[index]['top'][1] - 1]),
        Vertex(*VERTEX[segments[index]['top'][0] - 1])
    ]
    outer_trailing = [
        Vertex(*VERTEX[segments[index - 1]['top'][1] - 1]),
        Vertex(*VERTEX[segments[index - 1]['top'][0] - 1])
    ]
    logging.debug('join: segments: %s, %s', outer_leading, outer_trailing)
    inner_leading = [
        Vertex(*VERTEX[segments[index]['top'][2] - 1]),
        Vertex(*VERTEX[segments[index]['top'][3] - 1])
    ]
    inner_trailing = [
        Vertex(*VERTEX[segments[index - 1]['top'][2] - 1]),
        Vertex(*VERTEX[segments[index - 1]['top'][3] - 1])
    ]
    new_point = intersection(
        *[line_formula(*line)
          for line in [outer_leading, outer_trailing]])
    logging.debug('intersection: %s', new_point)
    # port bow of the first segment, and port quarter of second, now
    # become the point of intersection
    # pylint: disable=invalid-sequence-index  # get rid of bogus lint error
    vertex = outer_trailing[1].index
    replacement = VERTEX[vertex] = outer_trailing[1]._replace(
        x=new_point.x, y=new_point.y)
    outer_trailing[1] = replacement
    logging.debug('outer_trailing now: %s', outer_trailing)
    # now for the hull below; assume index is at offset 4
    VERTEX[vertex + 4] = VERTEX[vertex + 4]._replace(
        x=new_point.x, y=new_point.y)
    # now also correct port quarter of leading segment, deck and hull below
    vertex = outer_leading[0].index
    replacement = VERTEX[vertex] = outer_leading[0]._replace(
        x=new_point.x, y=new_point.y)
    outer_leading[0] = replacement
    VERTEX[vertex + 4] = VERTEX[vertex + 4]._replace(
        x=new_point.x, y=new_point.y)
    # now the same for the inner lines
    new_point = intersection(
        *[line_formula(*line)
          for line in [inner_leading, inner_trailing]])
    logging.debug('intersection: %s', new_point)
    vertex = inner_trailing[1].index
    replacement = VERTEX[vertex] = inner_trailing[1]._replace(
        x=new_point.x, y=new_point.y)
    inner_trailing[1] = replacement
    logging.debug('inner_trailing now: %s', inner_trailing)
    VERTEX[vertex + 4] = VERTEX[vertex + 4]._replace(
        x=new_point.x, y=new_point.y)
    vertex = inner_leading[0].index
    replacement = VERTEX[vertex] = inner_leading[0]._replace(
        x=new_point.x, y=new_point.y)
    inner_leading[0] = replacement
    VERTEX[vertex + 4] = VERTEX[vertex + 4]._replace(
        x=new_point.x, y=new_point.y)

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

def intersection(line0, line1):
    '''
    calculate intersection of two lines, given their formulas

    this assumes that the lines are different and that they do
    indeed intersect; it is meant for purposes of this program and
    not as a general solution.

    for example, line0: m = 1, c = 0 and line1: m = -1, c = -5
    putting the slopes on one side and the constants on the other, you get
    2x = -5, yielding x = -2.5, and thus y by the first formula,
    1 * -2.5 + 0, is also -2.5.
    '''
    if 'm' in line0 and 'm' in line1:
        # put the `mx`s on one side of the equation and `c`s on the other
        # then divide by the x multiplier, leaving x
        x_value = line1['c'] - line0['c'] / (line0['m'] - line1['m'])
    elif 'x' in line0:
        line0, line1 = line1, line0  # swap them
        x_value = line1['x']
    y_value = line0['m'] * x_value + line0['c']
    logging.debug('intersection: (%.3f, %.3f)', x_value, y_value)
    return Triplet(x_value, y_value)

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
            if color in COLOR:
                logging.debug('color %s already in COLOR: %s', color, COLOR)
                group = 'mtl%d' % COLOR.index(color)
            else:
                group = 'mtl%d' % len(COLOR)
                COLOR.append(color)
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

            you're the captain, steering, and "top left" is the port bow.
            the vertices are numbered counterclockwise: port quarter, starboard
            quarter, starboard bow. those are the last to be printed, since the
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
        FACE.append(segments[0]['start'])  # near end cap
        for segment in segments:
            FACE.extend([
                segment[k] for k in ('top', 'left', 'bottom', 'right')
            ])
        FACE.append(segments[-1]['end'])  # far end cap

        # now join the segments seamlessly

        for index in range(1, len(segments)):
            join(index, segments)

        DEVICE['Path'] = []  # clear path after stroke

    def showpage():
        for vertex in VERTEX:
            print('v %f %f %f' % vertex[:3], file=OUTPUT.obj)
        for face in FACE:
            print('f', *face, file=OUTPUT.obj)

    words = locals()
    words['='] = _print
    return words

if __name__ == '__main__':
    convert(*sys.argv[1:])
