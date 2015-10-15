from string import ascii_letters, digits
from collections import namedtuple, Counter
from sortedcontainers import SortedDict

identifier = 0

class SizeSelector(object):
    def __init__(self, scale = 1, sizes = None):
        if isinstance(scale, int): self.scale = scale
        else: self.scale = 1
        if isinstance(sizes, Counter): self.sizes = sizes
        else: self.sizes = Counter()

    @property
    def no_estimate_possible(self):
        if self.sizes: return False
        return True

    @property
    def size_estimate(self):
        return self.scale * self.sizes.most_common(1)[0][0]

    def add_possible_size(self, size):
        if not isinstance(size, int): raise TypeError()
        self.sizes.update([size // self.scale])

    def scaled_selector(self, scale):
        if not isinstance(scale, int): raise TypeError()
        return SizeSelector(self.scale * scale, self.sizes)

class Structure(object):
    def __init__(self, size = None):
        if isinstance(size, int): self.presize = size
        else: self.presize = SizeSelector()

    def description(self, label = None, specifiers = None):
        descriptors = []
        if specifiers is not None:
            descriptors.append(specifiers)
        try:
            try: descriptors.append(self.extra_name)
            except AttributeError: pass
            descriptors.append(self.name)
        except AttributeError:
            descriptors.append('void')
            try:
                size = self.size
                if size: descriptors.append('<size = {:d} byte>'.format(size))
            except AttributeError: pass
        if label is not None:
            descriptors.append(label)
        return ' '.join(descriptors)

    @property
    def size(self):
        if isinstance(self.presize, SizeSelector): 
            if self.presize.no_estimate_possible: raise AttributeError('size is unknown')
            self.presize = self.presize.size_estimate
        return self.presize

    @size.setter
    def size(self, size):
        if isinstance(self.presize, int) and self.presize != size: raise ValueError()
        self.presize = size

    def add_possible_size(self, size):
        if not isinstance(size, int): raise TypeError()
        if isinstance(self.presize, SizeSelector): self.presize.add_possible_size(size)
        elif size != self.presize: raise ValueError()

void = Structure(0)

class Data(Structure):
    def __init__(self, name = '', substructures = None, size = None):
        super().__init__(size)

        try: invalid_name = name[0] not in ascii_letters or any(character not in ascii_letters + digits + '_' for character in name[1:])
        except (TypeError, IndexError): invalid_name = True

        if invalid_name:
            global identifier
            self.name = '#{:d}'.format(identifier)
            identifier += 1
        else: self.name = name

        self.substructures = SortedDict()
        if isinstance(substructures, list):
            for substructure in substructures:
                self.add_substructure(substructure)

    def add_substructure(self, substructure):
        if not isinstance(substructure, Substructure): raise TypeError()
        if substructure.offset in self.substructures: raise ValueError(self.description(), substructure.description())
        if isinstance(substructure.structure.structure.presize, int):
            size = substructure.structure.structure.size
            next_key = self.substructures.bisect(substructure.offset)
            if next_key != self.substructures.bisect(substructure.offset + size): raise ValueError()
            elif next_key >= len(self.substructures) and isinstance(self.presize, int):
                if self.size <= substructure.offset + size: raise ValueError()
        self.substructures[substructure.offset] = substructure

    def annotate_size(self):
        self.annotate_size = lambda: None

class DataEnumeration(Data):
    def __init__(self, *arguments, **keyword_arguments):
        super().__init__(*arguments, **keyword_arguments)
        self.extra_name = 'enumeration'

class DataStructure(Data):
    def __init__(self, *arguments, **keyword_arguments):
        super().__init__(*arguments, **keyword_arguments)
        self.extra_name = 'structure'

class DataClass(Data):
    def __init__(self, *arguments, **keyword_arguments):
        super().__init__(*arguments, **keyword_arguments)
        self.extra_name = 'class'

class DataUnion(Data):
    def __init__(self, *arguments, **keyword_arguments):
        super().__init__(*arguments, **keyword_arguments)
        self.extra_name = 'union'
        self.options_count = 0

    def add_substructure(self, substructure):
        if not isinstance(substructure, Substructure): raise TypeError()
        self.substructures[self.options_count] = substructure
        self.options_count += 1

class Array(Structure):
    def __init__(self, cell = None, count = 0, size = None):
        if isinstance(cell, SpecificStructure): self.cell = cell
        else: self.cell = SpecificStructure()
        if isinstance(count, int): self.count = count
        else: self.count = 0
        if isinstance(size, int): self.cell.size = size // self.count

    def description(self, label = None, specifiers = None):
        descriptors = []
        if specifiers is not None: descriptors.append(specifiers)
        descriptors.append(self.cell.description(label))
        return ' '.join(descriptors) + '[{:d}]'.format(self.count)

    @property
    def presize(self):
        if isinstance(self.cell.structure.presize, SizeSelector):
            return self.cell.structure.presize.scaled_selector(self.count)
        return self.cell.structure.presize * self.count

    @presize.setter
    def presize(self, size):
        self.cell.structure.presize = size // self.count

    @property
    def substructures(self):
        substructures = SortedDict()
        for x in range(self.count):
            cell_offset = x * self.cell.structure.size
            substructures[cell_offset] = Substructure(self.cell, offset = cell_offset)
        return substructures

class Pointer(Structure):
    pointer_size = Counter()

    def __init__(self, destination = None, size = None):
        if isinstance(size, int): self.size = size
        if isinstance(destination, SpecificStructure): self.destination = destination
        else: self.destination = SpecificStructure(void)

    def description(self, label = None, specifiers = None):
        descriptors = [self.destination.description(), '*']
        if specifiers is not None: descriptors.append(specifiers)
        if label is not None: descriptors.append(label)
        return ' '.join(descriptors)

    @property
    def presize(self):
        return type(self).pointer_size

    @presize.setter
    def presize(self, size):
        type(self).pointer_size = size

class Function(Structure):
    def __init__(self, return_type = None, argument_types = None, size = None):
        super().__init__(size)
        global identifier
        self.name = '#{:d}'.format(identifier)
        identifier += 1
        
        if isinstance(return_type, Structure): self.return_type = return_type
        else: self.return_type = void

        self.argument_types = []
        if isinstance(argument_types, list):
            for argument_type in argument_types:
                if isinstance(argument_type, SpecificStructure):
                    self.argumet_types.append(argument_type)

    def description(self, label = None, specifiers = None):
        descriptors = [self.return_type.description(), self.name]
        descriptors.append('(' + ','.join(map(lambda argument_type: argument_type.description(), self.argument_types)) + ')')
        if specifiers is not None: descriptors.append(specifiers)
        if label is not None: descriptors.append(label)

    def add_argument_type(self, argument_type):
        if not isinstance(argument_type, SpecificStructure): raise TypeError()
        self.argument_types.append(argument_type)

class SpecificStructure(namedtuple('SpecificStructure', ['structure', 'constant', 'volatile'])):
    def __new__(self_class, structure, constant = False, volatile = False):
        if not isinstance(structure, Structure): raise TypeError()
        return super(SpecificStructure, self_class).__new__(self_class, structure, constant, volatile)

    def description(self, label = None):
        specifiers = []
        if self.constant: specifiers.append('constant')
        if self.volatile: specifiers.append('volatile')

        if specifiers: return self.structure.description(label, ' '.join(specifiers))
        return self.structure.description(label)

class Substructure(namedtuple('Substructure', ['structure', 'label', 'offset'])):
    def __new__(self_class, structure, label = '', offset = 0):
        if not isinstance(label, str): label = ''
        if not isinstance(offset, int): offset = 0
        if not isinstance(structure, SpecificStructure): raise TypeError()
        return super().__new__(self_class, structure, label, offset)

    def description(self):
        return self.structure.description(self.label)

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

        if field and not any(imbalance.values()): yield ''.join(field).strip()

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

    def parse_specific_pointer(pointer_partition, structure):
        while pointer_partition[1]:
            pointer_partition = pointer_partition[2].partition('*')
            constant, keywords = parse_keyword(pointer_partition[0], 'const')
            volatile, keywords = parse_keyword(keywords, 'volatile')
            if keywords: raise ValueError()

            structure = SpecificStructure(Pointer(structure), constant, volatile)
        return structure

    def parse_specific_structure(field):
        if field == 'void': return SpecificStructure(void)

        pointer_partition = field.partition('*')

        constant, name = parse_keyword(pointer_partition[0], 'const')
        volatile, name = parse_keyword(name, 'volatile')

        is_enumeration, name = parse_keyword(name, 'enum')
        is_structure,   name = parse_keyword(name, 'struct')
        is_union,       name = parse_keyword(name, 'union')
        is_class,       name = parse_keyword(name, 'class')

        if not (is_enumeration or is_structure or is_union or is_class):
            structure = Data(name)
        elif is_enumeration and not (is_structure or is_union):
            structure = DataEnumeration(name)
        elif is_structure and not (is_enumeration or is_union or is_class):
            structure = DataStructure(name)
        elif is_union and not (is_enumeration or is_structure or is_class):
            structure = DataUnion(name)
        elif is_class and not (is_enumeration or is_structure or is_union):
            structure = DataClass(name)
        else: raise ValueError()

        structure = SpecificStructure(structure, constant, volatile)
        return parse_specific_pointer(pointer_partition, structure)

    def parse_general_structure(field):
        function_partition = field.partition('()')
        structure = parse_specific_structure(function_partition[0])

        if function_partition[1]:
            print('function')
            return_type, constant, volatile = structure
            if not constant == volatile == False: raise ValueError()

            function_partition = function_partition[2].partition('(')
            if not function_partition[1]: raise ValueError()
            function_partition = function_partition[2].partition(')')
            if not function_partition[1]: raise ValueError()

            function = Function(return_type)
            arguments = parse_fields(function_partition[0])
            for argument in arguments:
                if argument == 'void': break
                function.add_argument_type(parse_general_structure(argument))

            pointer_partition = function_partition[2].strip().partition('*')
            if pointer_partition[0] or not pointer_partition[1]: raise ValueError()
            return parse_specific_pointer(pointer_partition, function)

        return structure

    def parse_structure(line, depth = 0, substructure = False):
        try: segments = line.strip().split(separators[depth])
        except IndexError: segments = [line.strip()]

        print(segments)

        fields = tuple(parse_fields(segments[0]))

        if not substructure: 
            structure = Data(fields[0])

            for segment in segments[1:]:
                structure.add_substructure(parse_structure(segment, depth + 1, True))

            try: structure.size = int(fields[1])
            except (IndexError, ValueError): pass

            return structure

        structure = parse_general_structure(fields[0])

        try:
            for segment in segments[1:]:
                structure.structure.add_substructure(parse_structure(segment, depth + 1, True))
        except AttributeError: raise ValueError()

        try:
            label = fields[1]
            array_partition = label.partition('[')

            if array_partition[1]:
                label = array_partition[0].strip()

                array_partition = array_partition[2].partition(']')
                if not array_partition[1] or array_partition[2]: raise ValueError()

                try: structure = SpecificStructure(Array(structure, int(array_partition[0])))
                except ValueError: structure = SpecificStructure(Array(structure))
        except IndexError: label = None

        try: structure.structure.size = int(fields[3])
        except (IndexError, ValueError): pass

        try: return Substructure(structure, label, int(fields[2]))
        except (IndexError, ValueError):
            return Substructure(structure, label)

    for line in lines:
        structure = parse_structure(line)
        structures[structure.name] = structure

    return structures
