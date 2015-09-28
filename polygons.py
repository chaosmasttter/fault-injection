from collections import namedtuple, defaultdict

Point = namedtuple('Point', ['x', 'y'])
Edge = namedtuple('Edge', ['start', 'vertical'])

class Square(namedtuple('Square', ['position', 'value'])):
    def __init__(self, position, value):
        x, y = position
        self.vertices = [Point(x, y), Point(x, y + 1), Point(x + 1, y + 1), Point(x + 1, y)]

    def edges(self):
        yield Edge(self.vertices[ 0], vertical = True)
        yield Edge(self.vertices[+1], vertical = False)
        yield Edge(self.vertices[-1], vertical = True)
        yield Edge(self.vertices[ 0], vertical = False)

    def as_polygon(self):
        return Polygon(self.vertices, self.value)

class Polygon(object):
    def __init__(self, vertices = [], value = None):
        self.vertices = vertices
        self.value = value

    def edge_vertex_points(self, number):
        start = 1 - len(self.vertices)
        return self.vertices[number], self.vertices[start + number]

def create_polygones(squares):
    polygons = {}
    edges = {}
    count = 0

    class Index(object):
        def __init__(self, polygon_number, edge_number):
            self.polygon_number = polygon_number
            self.edge_number = edge_number

    for square in squares:
        neighbours = defaultdict(list)
        free_edges = {}

        for number, edge in enumerate(square.edges()):
            if edge in edges:
                index = edges[edge]
                polygon = polygons[index.polygon_number]
                if square.value == polygon.value:
                    neighbours[polygon].append((index.edge_number, edge, number))
            free_edges[number] = edge

        if neighbours:
            pass

        else:
            polygon_number = count
            polygons[count] = square.as_polygon()
            count += 1

        for number, edge in free_edges.items():
            edges[edge] = Index(polygon_number, number)

    return polygons.values()
