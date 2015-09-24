from collections import namedtuple
from sortedcontainers import SortedDict

identifier = 0

class Structure(namedtuple('Structure', ['name', 'size', 'substructures'])):
    def __new__(self_class, name = '', size = None, substructures = None):
        if not name:
            name = '#{:d}'.format(identifier)
            identifier += 1
        if substructures is None: substructures = SortedDict()
        return super(DataStructure, self_class).__new__(self_class, name, size, substructures)

    def description(self, label = None):
        descriptors = [self.name]
        if label is not None:
            descriptors.append(self.label)
        if self.size is not None:
            descriptors.append('(size = {:d})'.format(self.size))
        return ' '.join(descriptors)

class DataEnumeration(Structure):
    def description(self, label = None):
        return 'enumeration ' + super(DataEnumeration, self).description(label)

class DataStructure(Structure):
    def description(self, label = None):
        return 'structure ' + super(DataStructure, self).description(label)

class DataUnion(Structure):
    def description(self, label = None):
        return 'union ' + super(DataUnion, self).description(label)

class DataClass(Structure):
    def description(self, label = None):
        return 'class ' + super(DataClass, self).description(label)

class Substructure(namedtuple('Substructure', ['structure', 'label', 'constant', 'offset'])):
    def __new__(self_class, structure, label = None, constant = False, offset = 0):
        return super(Substructure, self_class).__new__(self_class, structure, label, constant, offset)

    def description(self):
        return self.structure.description(self.label)

class Pointer(Substructure):
    def description(self):
        return self.structure.description('* ' + self.label)

def parse_recursive(string):
    separators = ';&$%?#@'
    structures = {}
    
    lines = string.strip().split('\n')

    def parse_fields(fields):
        count = 0
	field = []

	for char in fields:
	    if count == 0 and char == ',':
	        yield ''.join(field).strip()
	        field = []
	        continue

	    if char == '<':
	        count += 1
	    if char == '>':
	        count -= 1
	
	    field.append(char)

        if field: yield ''.join(field).strip()

    def parse_structure(line, depth = 0, substructure = False):
        segments = line.strip().split(separators[depth])

        substructures = SortedDict()
        for segment in segments[1:]:
            sub = parse_structure(segment, depth + 1, substructure = True)
            substructures[sub.offset] = sub

        fields = tuple(parse_fields(segments[0].strip()))

        if len(fields) % 2 == 0:
            structure = Structure(fields[0], fields[-1], substructures)
        else: 
            structure = Structure(fields[0], substructures = substructures)

        if substructure: return Substructure(structure, fields[1], fields[2])
        else: return structure

    for line in lines:
        structure = parse_structure(line)
        structures[structure.name] = structure

    return structures
