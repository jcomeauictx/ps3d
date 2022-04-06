#!/usr/bin/python3
'''
Prototype of a 3D extension of postscript

Produces .obj files for 3d printing
'''
import sys

STACK = []

def convert(infile=sys.stdin, outfile=sys.stdout):
    '''
    convert .ps3d file to .obj format
    '''
    if infile != sys.stdin:
        infile = open(infile)
    if outfile != sys.stdout:
        outfile = open(outfile, 'w')
if __name__ == '__main__':
    convert(*sys.argv[1:])
