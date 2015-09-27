from collections import namedtuple

Point = namedtuple('Point', ['x', 'y'])

class Square(namedtuple('Square', ['position', 'value'])):
    def __init__(self, position, value):
        x, y = position
        self.coordinates = [Point(x, y), Point(x, y + 1), Point(x + 1, y + 1), Point(x + 1, y)]

    def sides(self):
        yield self.coordinates[0], self.coordinates[1]
        yield self.coordinates[1], self.coordinates[2]
        yield self.coordinates[2], self.coordinates[3]
        yield self.coordinates[3], self.coordinates[0]

class Polygon(object):
    def __init__(self, coordinates = [], value = None):
        self.coordinates = coordinates
        self.value = value

def create_polygones(squares):
    polygons = []
    sides = {}
    count = 0

    class Index(object):
        def __init__(self, polygon_number, coordinate_number):
            self.polygon_number = polygon_number
            self.side_number = side_number

    for square in squares:
        for side in square.sides():
            if side in sides:
                index = sides[side]


                
