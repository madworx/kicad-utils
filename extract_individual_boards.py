#!/usr/bin/python

import pcbnew
import sys
import itertools
import operator
from setuptools_scm import get_version

board = pcbnew.LoadBoard("full.kicad_pcb")

def is_vertical(path):
    return path.start.real == path.end.real

def is_horizontal(path):
    return path.start.imag == path.end.imag

class Rect(object):
    def __init__(self,x1,y1,x2,y2):
        self.x1 = min(set([(line.start.real) for line in set([x1,y1,x2,y2])])) - 10000
        self.y1 = min(set([(line.start.imag) for line in set([x1,y1,x2,y2])])) - 10000
        self.x2 = max(set([(line.end.real) for line in set([x1,y1,x2,y2])])) + 10000
        self.y2 = max(set([(line.end.imag) for line in set([x1,y1,x2,y2])])) + 10000

class Line(object):
    def __init__(self,start,end):
        self.start = start
        self.end = end

        # Ensure that start.x < end.x
        if self.start.real > self.end.real:
           tmp = self.start
           self.start = self.end
           self.end = tmp

    def __repr__(self):
        return "<({};{})-({};{})>".format(self.start.real,self.start.imag,self.end.real,self.end.imag)

    def __eq__(self, other):
        return self.start == other.start and self.end == other.end

# https://stackoverflow.com/questions/49068622/efficient-algorithm-to-find-rectangles-from-lines
def find_rectangles(paths):
    vertical_paths = filter(lambda path: is_vertical(path), paths)
    horizontal_paths = filter(lambda path: is_horizontal(path), paths)

    vertical_paths.sort(key=lambda path: path.start.imag, reverse=True)
    horizontal_paths.sort(key=lambda path: path.start.real)

    potential_rectangles = []
    for i,h1 in enumerate(horizontal_paths[:-1]):
        for h2 in horizontal_paths[i+1:]:
            if ((h1.start.real == h2.start.real)
                    and (h1.end.real == h2.end.real)):
                potential_rectangles.append([h1,h2,None,None])

    rectangles = []
    for v in vertical_paths:
        for i,(h1,h2,v1,v2) in enumerate(potential_rectangles):
            if v1 is None and v.start == h1.start and v.end == h2.start:
                potential_rectangles[i][2] = v
                if v2 is not None:
                    rectangles.append(potential_rectangles.pop(i))
                break
            if v2 is None and v.start == h1.end and v.end == h2.end:
                potential_rectangles[i][3] = v
                if v1 is not None:
                    rectangles.append(potential_rectangles.pop(i))
                break

    return rectangles

def prune_others(board,rect):
    """Prune all objects (modules, lines, etc) outside of rect"""
    to_prune = []
    for draw in board.GetDrawings():
        if pcbnew.DRAWSEGMENT_ClassOf(draw):
            if not(draw.GetStart().x >= rect.x1 \
               and draw.GetStart().x <= rect.x2 \
               and draw.GetStart().y >= rect.y1 \
               and draw.GetStart().y <= rect.y2):
                to_prune.append(draw)
        else:
            if not(draw.GetPosition().x >= rect.x1 \
               and draw.GetPosition().x <= rect.x2 \
               and draw.GetPosition().y >= rect.y1 \
               and draw.GetPosition().y <= rect.y2):
                to_prune.append(draw)
    #print "Pruning {} drawings.".format(len(to_prune))
    for prune in to_prune:
        board.Remove(prune)

    for mod in board.GetModules():
        if not(mod.GetPosition().x >= rect.x1 \
           and mod.GetPosition().x <= rect.x2 \
           and mod.GetPosition().y >= rect.y1 \
           and mod.GetPosition().y <= rect.y2):
            board.Remove(mod)

    for track in board.GetTracks():
        if track.GetStart().x > rect.x2 or track.GetStart().x < rect.x1 \
           or track.GetStart().y > rect.y2 or track.GetStart().y < rect.y1:
            board.Remove(track)

    done = False
    while(not done):
        for i in range(board.GetAreaCount(),-1,-1):
            done = True
            area = board.GetArea(i) # pcbnew.ZONE_CONTAINER
            if area is not None:
                if not(area.GetPosition().x >= rect.x1 \
                   and area.GetPosition().x <= rect.x2 \
                   and area.GetPosition().y >= rect.y1 \
                   and area.GetPosition().y <= rect.y2):
                    board.RemoveArea(None, area)
                    done = False
                    break

def get_edge_cuts(board):
    paths = []
    for segment in board.GetDrawings():
        if pcbnew.DRAWSEGMENT_ClassOf(segment) and \
        board.GetLayerName(segment.GetLayer()) == 'Edge.Cuts':
            path = Line(complex(segment.GetStart().x,segment.GetStart().y),complex(segment.GetEnd().x,segment.GetEnd().y))
            paths.append(path)
    return paths

paths = get_edge_cuts(board)
rects = []
for rect in find_rectangles(paths):
    rects.append(Rect(rect[0],rect[1],rect[2],rect[3]))
rects.sort(key = lambda r: (r.y1,r.x1))

version = get_version(root='..', relative_to=__file__)
print version
sys.exit(1)
print "Identified {} PCB rectangles from {} unique Edge.Cuts.".format(len(rects),len(paths))

i = 0
for rect in rects:
    i = i + 1
    print "Found PCB #{} at {};{} -- {};{}".format(i,rect.x1,rect.y1,rect.x2,rect.y2)
    board = pcbnew.LoadBoard("full.kicad_pcb")
    prune_others(board,rect)
    pcbnew.SaveBoard("board-{}.kicad_pcb".format(i),board)
