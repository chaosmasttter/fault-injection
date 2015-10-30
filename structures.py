from string import ascii_letters, digits
from collections import namedtuple, Counter
from sortedcontainers import SortedDict

identifier = 0

class SizeSelector(object):
    def __init__(self, scale = 1, sizes = None):
        if isinstance(scale, int) and scale: self.scale = scale
        else: self.scale = 1
        if isinstance(sizes, Counter): self.sizes = sizes
        else: self.sizes = Counter()

    @property
    def no_estimate_possible(self):
        if self.sizes: return False
        return True

    @property
    def size_estimate(self):
        most_common = self.sizes.most_common()
        estimate, rate = most_common[0]
        for size, count in most_common[1:]:
            if count != rate: break
            if size < estimate: estimate = size

        return self.scale * estimate

    def add_possible_size(self, size):
        assert isinstance(size, int)
        self.sizes.update([size // self.scale])

    def remove_possible_sizes_above(self, limit):
        assert isinstance(limit, int)
        assert all( isinstance(size, int) for size in self.sizes.keys() )
        self.sizes = Counter(filter(lambda size: size <= limit, self.sizes.elements()))

    def remove_possible_sizes_below(self, limit):
        assert isinstance(limit, int)
        assert all( isinstance(size, int) for size in self.sizes.keys() )
        self.sizes = Counter(filter(lambda size: size >= limit, self.sizes.elements()))

    def scaled_selector(self, scale):
        assert isinstance(scale, int)
        assert all( isinstance(size, int) for size in self.sizes.keys() )
        return SizeSelector(self.scale * scale, self.sizes)

class Structure(object):
    def __init__(self, size = None):
        if isinstance(size, int):
            self.presize = size
            self.size_known = True
        else:
            self.presize = SizeSelector()
            self.size_known = False
        self.known = False

    def description(self, label = None, specifiers = None):
        descriptors = []
        if specifiers is not None:
            assert isinstance(specifiers, str)
            descriptors.append(specifiers)
        try:
            descriptors.append(self.full_name)
        except AttributeError:
            descriptors.append('void')
            try:
                assert isinstance(self.size, int)
                size = self.size
                if size: descriptors.append('<size = {:d} byte>'.format(size))
            except AttributeError: pass
        if label is not None:
            assert isinstance(label, str)
            descriptors.append(label)
        return ' '.join(descriptors)

    @property
    def size(self):
        if not self.size_known:
            assert isinstance(self.presize, SizeSelector)
            if self.presize.no_estimate_possible: raise AttributeError('size is unknown')
            self.presize = self.presize.size_estimate
            self.size_known = True
        assert isinstance(self.presize, int)
        return self.presize

    @size.setter
    def size(self, size):
        assert isinstance(size, int)
        if not self.size_known: 
            self.presize = size
            self.size_known = True
        else: assert self.presize == size

    @property
    def possible_size_known(self):
        return self.size_known or not self.presize.no_estimate_possible

    def add_possible_size(self, size):
        assert isinstance(size, int)
        if not self.size_known:
            assert isinstance(self.presize, SizeSelector)
            self.presize.add_possible_size(size)
        else: assert self.size <= size

    def remove_possible_sizes_above(self, limit):
        assert isinstance(limit, int)
        if not self.size_known:
            assert isinstance(self.presize, SizeSelector)
            self.presize.remove_possible_sizes_above(limit)
        else: assert self.size <= limit

    def remove_possible_sizes_below(self, limit):
        assert isinstance(limit, int)
        if not self.size_known:
            assert isinstance(self.presize, SizeSelector)
            self.presize.remove_possible_sizes_below(limit)
        else: assert self.size >= limit

    def same(self, other):
        if self is other: return True
        if type(self) is not type(other): return False
        if self.size_known and other.size_known and self.size != other.size: return False

void = Structure(0)

class Data(Structure):
    def __init__(self, name = '', substructures = None, size = None):
        super().__init__(size)

        real_name = name.partition('<')[0] + name.rpartition('>')[2]
        try: invalid_name = name[0] not in ascii_letters or any(
               character not in ascii_letters + digits + '_ ' for character in real_name[1:])
        except (TypeError, IndexError): invalid_name = True

        if invalid_name:
            global identifier
            assert isinstance(identifier, int)
            self.name = '#{:d}'.format(identifier)
            identifier += 1
        else: self.name = name

        try: self.substructures
        except AttributeError: self.substructures = SortedDict()
        if isinstance(substructures, list):
            for substructure in substructures:
                self.add_substructure(substructure)

    @property
    def full_name(self):
        name_parts = []
        try:
            assert isinstance(self.extra_name, str)
            name_parts.append(self.extra_name)
        except AttributeError: pass
        name_parts.append(self.name)
        return ' '.join(name_parts)

    def add_substructure(self, substructure):
        assert isinstance(substructure, Substructure)

        assert substructure.offset not in self.substructures
        if substructure.size_known:
            assert isinstance(substructure.presize, int)
            try: assert self.substructures.keys()[self.substructures.bisect(substructure.offset)] >= substructure.offset + substructure.size
            except IndexError: assert not self.size_known or self.size >= substructure.offset + substructure.size

        self.substructures[substructure.offset] = substructure

    def add_possible_size(self, size):
        assert isinstance(size, int)
        super().add_possible_size(size)
        self.annotate_size()

    def annotate_size(self):
        if self.substructures:
            substructures = reversed(self.substructures.values())

            last_substructure = next(substructures)
            last_done = self.annotate_size_of_last_substructure(last_substructure)
            upper_bound = last_substructure.offset

            for substructure in substructures:
                possible_size = upper_bound - substructure.offset
                substructure.remove_possible_sizes_above(possible_size)
                substructure.add_possible_size(possible_size)
                upper_bound = substructure.offset

            self.annotate_size = lambda: self.annotate_size_of_last_substructure(last_substructure)
        self.annotate_size = lambda: None

    def annotate_size_of_last_substructure(self, substructure):
        assert isinstance(substructure, Substructure)

        if substructure.size_known:
            assert isinstance(substructure.presize, int)
            self.remove_possible_sizes_below(substructure.offset + substructure.size)
        elif self.size_known:
            assert isinstance(self.presize, int)
            possible_size = self.size - substructure.offset
            substructure.remove_possible_sizes_above(possible_size)
            substructure.add_possible_size(possible_size)
        else: return
        self.annotate_size = self.annotate_size_of_last_substructure = lambda: None

    def same(self, other):
        if self is other: return True
        if type(self) == Array or type(other) == Array and type(self) != type(other): return False
        if not isinstance(other, type(self)) and not isinstance(self, type(other)): return False
        if self.full_name == other.full_name: return True
        if type(self) is not type(other) and self.name == other.name: return True
        if '#' not in self.name and '#' not in other.name: return False
        if self.size_known and other.size_known and self.size != other.size: return False
        if len(self.substructures) != len(other.substructures): return False
        if type(self) is not type(other) and len(self.substructures) == 0: return False

        try: self_substructures = self.substructures.values()
        except AttributeError: self_substructures = self.substructures
        try: other_substructures = other.substructures.values()
        except AttributeError: other_substructures = other.substructures

        return all(self_substructure.same(other_substructure)
                   for self_substructure, other_substructure
                   in zip(self_substructures, other_substructures))

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
        self.substructures = []
        super().__init__(*arguments, **keyword_arguments)
        self.extra_name = 'union'

    def add_substructure(self, substructure):
        assert isinstance(substructure, Substructure)
        assert not substructure.offset
        self.substructures.append(substructure)

    def annotate_size(self):
        if self.size_known:
            assert isinstance(self.presize, int)
            for substructure in self.substructures:
                substructure.remove_possible_sizes_above(self.size)
                substructure.add_possible_size(self.size)
            self.annotate_size = lambda: None

        else:
            biggest_size = 0
            for substructure in self.substurctures:
                assert not substructure.offset
                if substructure.size_known:
                    assert isinstance(substructure.presize, int)
                    biggest_size = max(substructure.size, biggest_size)
                else:
                    biggest_size = None
                    break
            if biggest_size is not None:
                self.remove_possible_sizes_below(biggest_size)
                self.add_possible_size(biggest_size)
                self.annotate_size = lambda: None

    def annotate_size_of_last_substructure(self, substructure): pass

class Array(Data):
    def __init__(self, cell, count = 0, size = None):
        assert isinstance(cell, SpecificStructure)
        self.cell = cell
        if isinstance(count, int): self.count = count
        else: self.count = 0
        if isinstance(size, int): self.cell.size = size // self.count
        self.extra_name = '[{:d}]'.format(self.count)
        self.name = self.cell.description() + self.extra_name

    def description(self, label = None, specifiers = None):
        descriptors = []
        if specifiers is not None:
            assert isinstance(specifiers, str)
            descriptors.append(specifiers)
        descriptors.append(self.cell.description(label))
        return ' '.join(descriptors) + self.extra_name

    @property
    def size_known(self):
        return self.cell.structure.size_known

    @size_known.setter
    def size_known(self, boolean):
        assert isinstance(boolean, bool)
        self.cell.structure.size_known = boolean

    @property
    def presize(self):
        if isinstance(self.cell.structure.presize, SizeSelector):
            return self.cell.structure.presize.scaled_selector(self.count)
        assert isinstance(self.cell.structure.presize, int)
        return self.cell.structure.presize * self.count

    @presize.setter
    def presize(self, size):
        assert isinstance(size, int)
        self.cell.structure.presize = size // self.count

    @property
    def substructures(self):
        substructures = SortedDict()
        for x in range(self.count):
            cell_offset = x * self.cell.structure.size
            substructures[cell_offset] = Substructure(self.cell, offset = cell_offset)
        return substructures

    def add_substructure(self, substructure): pass

    def annotate_size(self): pass
    def annotate_size_of_last_substructure(self, substructure): pass

    def same(self, other):
        same = Structure.same(self, other)
        if same is not None: return same
        return self.count == other.count and self.cell.same(other.cell)

class Pointer(Structure):
    pointer_size = SizeSelector()
    pointer_size_known = False

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
    def size_known(self):
        return type(self).pointer_size_known

    @size_known.setter
    def size_known(self, boolean):
        assert isinstance(boolean, bool)
        type(self).pointer_size_known = boolean

    @property
    def presize(self):
        return type(self).pointer_size

    @presize.setter
    def presize(self, size):
        assert isinstance(size, int)
        type(self).pointer_size = size

    def same(self, other):
        same = Structure.same(self, other)
        if same is not None: return same
        return self.destination.same(other.destination)

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
        descriptors.append('(' + ', '.join(map(lambda argument_type: argument_type.description(), self.argument_types)) + ')')
        if specifiers is not None:
            assert isinstance(specifiers, str)
            descriptors.append(specifiers)
        if label is not None:
            assert isinstance(label, str)
            descriptors.append(label)
        return ' '.join(descriptors)

    def add_argument_type(self, argument_type):
        assert isinstance(argument_type, SpecificStructure)
        self.argument_types.append(argument_type)

    def same(self, other):
        same = Structure.same(self, other)
        if same is not None: return same
        if not self.return_type.same(other.return_type): return False
        return all(self_argument_type.same(other_argument_type)
                   for self_argument_type, other_argument_type
                   in zip(self.argument_types, other.argument_types))

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

    def same(self, other):
        if type(self) is not type(other): return False
        if self[1:] is not other[1:]: return False
        return self.structure.same(other.strurcture)

class Substructure(namedtuple('Substructure', ['structure', 'label', 'offset'])):
    def __new__(self_class, structure, label = '', offset = 0):
        if not isinstance(label, str): label = ''
        if not isinstance(offset, int): offset = 0
        if not isinstance(structure, SpecificStructure): raise TypeError()
        return super().__new__(self_class, structure, label, offset)

    @property
    def size_known(self):
        return self.structure.structure.size_known

    @property
    def possible_size_known(self):
        return self.structure.structure.possible_size_known

    @property
    def presize(self):
        return self.structure.structure.presize

    @property
    def size(self):
        return self.structure.structure.size

    def description(self):
        return self.structure.description(self.label)

    def add_possible_size(self, size):
        self.structure.structure.add_possible_size(size)

    def remove_possible_sizes_above(self, limit):
        self.structure.structure.remove_possible_sizes_above(limit)

    def remove_possible_sizes_below(self, limit):
        self.structure.structure.remove_possible_sizes_below(limit)

    def same(self, other):
        if type(self) is not type(other): return False
        if self[1:] is not other[1:]: return False
        return self.structure.same(other.sturcture)

def parse_structures_recursive(string):
    if string is None: return {}
    separators = ';&$%?#@'
    data_structures = {}
    functions = []
    pointers = []

    def lookup_data_structure(structure):
        assert isinstance(structure, Data)
        if structure.name in data_structures:
            lookup_structure = data_structures[structure.name]
            assert structure.same(lookup_structure)
            return lookup_structure

    def lookup_structure(structure, structure_list):
        assert isinstance(structure, Structure)
        for other_structure in structure_list:
            if structure.same(other_structure):
                return other_structure

    def update_structure(structure, other_structure):
        assert isinstance(structure, Data)
        assert structure.same(other_structure)
        if '#' in structure.name and '#' not in other_structure.name:
            structure.name = other_structure.name
        if not isinstance(structure, type(other_structure)):
            assert isinstance(other_structure, type(structure))
            new_structure = type(other_structure)(structure.name)
            new_structure.substructures = structure.substructures
            new_structure.presize = structure.presize
            new_structure.size_known = structure.size_known
            data_structures[new_structure.name] = new_structure
            return new_structure
        return structure

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

    def parse_specific_pointer(pointer_partition, structure, known):
        while pointer_partition[1]:
            pointer_partition = pointer_partition[2].partition('*')
            constant, keywords = parse_keyword(pointer_partition[0], 'const')
            volatile, keywords = parse_keyword(keywords, 'volatile')
            assert not keywords

            pointer = Pointer(structure)
            lookup = lookup_structure(pointer, pointers)
            if not lookup:
                pointers.append(pointer)
                known = False
            else: pointer, known = lookup, True
            structure = SpecificStructure(pointer, constant, volatile)
        return structure, known

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
        else: assert False

        lookup = lookup_data_structure(structure)
        if not lookup:
            data_structures[structure.name] = structure
            known = lookup
        else:
            lookup = update_structure(lookup, structure)
            structure, known = lookup, True

        structure = SpecificStructure(structure, constant, volatile)
        return parse_specific_pointer(pointer_partition, structure, known)

    def parse_general_structure(field):
        function_partition = field.partition('()')
        structure, known = parse_specific_structure(function_partition[0])

        if function_partition[1]:
            return_type, constant, volatile = structure
            assert constant == volatile == False

            function_partition = function_partition[2].partition('(')
            assert function_partition[1]
            function_partition = function_partition[2].partition(')')
            assert function_partition[1]

            function = Function(return_type)
            arguments = parse_fields(function_partition[0])
            for argument in arguments:
                if argument == 'void': break
                function.add_argument_type(parse_general_structure(argument)[0])

            lookup = lookup_structure(function, functions)
            if not lookup:
                functions.append(function)
                known = False
            else: function, known = lookup, True

            pointer_partition = function_partition[2].strip().partition('*')
            assert not pointer_partition[0] and pointer_partition[1]
            return parse_specific_pointer(pointer_partition, function, known)

        return structure, known

    def parse_structure(line, depth = 0, substructure = False):
        try: segments = line.strip().split(separators[depth])
        except IndexError: segments = [line.strip()]

        fields = tuple(parse_fields(segments[0]))

        if not substructure: 
            structure = Data(fields[0])
            lookup = lookup_data_structure(structure)
            if not lookup:
                for segment in segments[1:]:
                    structure.add_substructure(parse_structure(segment, depth + 1, True))
                    lookup = lookup_structure(structure, data_structures.values())
                    if lookup: lookup = update_structure(lookup, structure)
            if lookup: structure = lookup
            else: data_structures[structure.name] = structure

            try: structure.size = int(fields[1])
            except (IndexError, ValueError): pass

            return

        structure, known = parse_general_structure(fields[0])

        if not known:
            try:
                for segment in segments[1:]:
                    structure.structure.add_substructure(parse_structure(segment, depth + 1, True))
            except AttributeError: assert False

            if isinstance(structure.structure, Data):
                lookup = lookup_structure(structure.structure, data_structures.values())
                if lookup: lookup = update_structure(lookup, structure.structure)

                if known or lookup: structure = SpecificStructure(lookup, *structure[1:])
                else: data_structures[structure.structure.name] = structure.structure

        try:
            label = fields[1]
            array_partition = label.partition('[')

            if array_partition[1]:
                label = array_partition[0].strip()

                array_partition = array_partition[2].partition(']')
                assert array_partition[1] and not array_partition[2]

                try: count = int(array_partition[0])
                except ValueError: count = 0

                array = Array(structure, count)
                lookup = lookup_data_structure(array)
                if not lookup: data_structures[array.full_name] = array

                structure = SpecificStructure(array)
        except IndexError: label = None

        try: structure.structure.size = int(fields[3])
        except (IndexError, ValueError): pass

        try: return Substructure(structure, label, int(fields[2]))
        except (IndexError, ValueError):
            return Substructure(structure, label)

    lines = string.strip().split('\n')
    for line in lines: parse_structure(line)

    for structure in data_structures.values(): structure.annotate_size()
    return data_structures
