from collections import namedtuple
from sortedcontainers import SortedDict

identifier = 0

class Structure(namedtuple('Structure', ['name', 'size', 'substructures'])):
    def __new__(self_class, name = '', size = None, substructures = None):
        if not name:
            global identifier
            name = '#{:d}'.format(identifier)
            identifier += 1
        if substructures is None: substructures = SortedDict()
        return super(Structure, self_class).__new__(self_class, name, size, substructures)

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

class Substructure(namedtuple('Substructure', ['structure', 'label', 'offset'])):
    def __new__(self_class, structure, label = None, offset = 0):
        return super(Substructure, self_class).__new__(self_class, structure, label, offset)

    def description(self):
        return self.structure.description(self.label)

class SpecificStructure(namedtuple('SpecificStructure', ['structure', 'constant', 'volatile'])):
    def __new__(self_class, structure, constant = False, volatile = False):
        return super(SpecificStructure, self_class).__new__(self_class, structure, constant, volatile)

    def description(self, label = None):
        descriptor = self.structure.description(self.label)
        if constant: descriptor = 'constant ' + descriptor
        if volatile: descriptor = 'volatile ' + descriptor
        return descriptor

class Pointer(SpecificStructure):
    def description(self, lable = None):
        if constant: descriptors.append('constant')
        if volatile: descriptors.append('volatile')
        if label is not None: descriptors.append(label)
        return self.structure.description(' '.join(descriptors))

def parse_structures_recursive(string):
    if string is None: return {}
    separators = ';&$%?#@'
    structures = {}

    lines = string.strip().split('\n')

    def parse_fields(fields):
        imbalance = { '<>' : 0, '()' : 0 }
        field = []

        for char in fields:
            if not any(imbalance.values()) and char == ',':
                yield ''.join(field).strip()
                field = []
                continue

            elif char == '<':
                imbalance['<>'] += 1
            elif char == '>':
                imbalance['<>'] -= 1
            elif char == '(':
                imbalance['()'] += 1
            elif char == ')':
                imbalance['()'] -= 1
            field.append(char)

        if field: yield ''.join(field).strip()

    def parse_structure(line, depth = 0, substructure = False):
        try:               segments = line.strip().split(separators[depth])
        except IndexError: segments = [line.strip()]

        substructures = SortedDict()
        for segment in segments[1:]:
            sub = parse_structure(segment, depth + 1, substructure = True)
            substructures[sub.offset] = sub

        fields = tuple(parse_fields(segments[0].strip()))

        if not substructure:
            try:               size = fields[1]
            except IndexError: size = None

            return Structure(fields[0], size, substructures)

        try:               size = fields[3]
        except IndexError: size = None

        try:               offset = fields[2]
        except IndexError: offset = None

        try:               label = fields[1]
        except IndexError: label = None

        if '(' in fields[0] or ')' in fields[0]:
            return Substructure(Structure(fields[0], size, substructures), label, offset)

        pointer_partition = fields[0].partition('*')

        constant, name = parse_keyword(pointer_partition[0], 'const')
        volatile, name = parse_keyword(name, 'volatile')

        is_enumeration, name = parse_keyword(name, 'enum')
        is_structure,   name = parse_keyword(name, 'struct')
        is_union,       name = parse_keyword(name, 'union')
        is_class,       name = parse_keyword(name, 'class')

        if not (is_enumeration or is_structure or is_union or is_class):
            structure = Structure(name, size, substructures)
        elif is_enumeration and not (is_structure or is_union):
            structure = DataEnumeration(name, size, substructures)
        elif is_structure and not (is_enumeration or is_union or is_class):
            structure = DataStructure(name, size, substructures)
        elif is_union and not (is_enumeration or is_structure or is_class):
            structure = DataUnion(name, size, substructures)
        elif is_class and not (is_enumeration or is_structure or is_union):
            structure = DataClass(name, size, substructures)
        else: raise ValueError()

        structure = SpecificStructure(structure, constant, volatile)

        while pointer_partition[1]:
            pointer_partition = pointer_partition[2].partition('*')
            constant, keywords = parse_keyword(pointer_partition[0], 'const')
            volatile, keywords = parse_keyword(keywords, 'volatile')
            if keywords: raise ValueError()

            structure = Pointer(structure, constant, volatile)

        return Substructure(structure, label, offset)

    def parse_keyword(name, keyword):
        if not name: return False, name

        name = name.strip()
        partitions = name.partition(keyword)
        if not partitions[1]: return False, name

        if partitions[0]:
            preceding  = partitions[0][-1]
            if not  preceding.isspace(): return False, name
        if partitions[2]:
            succeeding = partitions[-1][0]
            if not succeeding.isspace(): return False, name

        return True, (partitions[0].strip() + ' ' + partitions[2].strip()).strip()

    for line in lines:
        structure = parse_structure(line)
        structures[structure.name] = structure

    return structures
