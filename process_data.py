#!/usr/bin/env python3

import re
import csv
import math
from sys import stdout
from bisect import bisect
from decimal import Decimal
from subprocess import check_output
from argparse import ArgumentParser
from tkinter import Tk

from sortedcontainers import SortedDict

from graphical_interface import Visualisation
from structures import parse_structures_recursive, Structure, Substructure, Data, DataUnion
from grouping import Interval, Grouping, Choice

class Result(object):
    """
    Result class describing the possible experiment results.

    Results are static defined constants. 
    Possible result constants are:
    - OK
    - WRONG
    - ASSERT_FAILED
    - DOUBLE_FAULT
    - GENERAL_PROTECTION_FAULT
    - USER_ERROR
    - OTHER_ERROR
    """

    OK, \
    WRONG, \
    ASSERT_FAILED, \
    DOUBLE_FAULT, \
    GENERAL_PROTECTION_FAULT, \
    USER_ERROR, \
    OTHER_ERROR = range(7)

    def __init__(self, names):
        self.parsers = []

        for name in names:
            if re.search('HEX', name): base = 16
            else: base = 10

            if re.search('bit_offset', name):
                def parse_bit(result, name = name, base = base):
                    self.bit = int(result[name], base)
                self.parsers.append(parse_bit)
            elif re.search('register_offset', name):
                def parse_register(result, name = name):
                    self.register = Register.read(result[name])
                self.parsers.append(parse_register)
            elif re.search('injection_address', name):
                def parse_address(result, name = name, base = base):
                    self.address = Memory.read(result[name], base)
                self.parsers.append(parse_address)
            elif re.search('injection_ip', name):
                def parse_instruction_pointer(result, name = name, base = base):
                    self.instruction_pointer = Memory.read(result[name], base)
                self.parsers.append(parse_instruction_pointer)
            elif re.search('time1', name):
                def parse_start_time(result, name = name, base = base):
                    self.start_time = int(result[name], base)
                self.parsers.append(parse_start_time)
            elif re.search('time2', name):
                def parse_end_time(result, name = name, base = base):
                    self.end_time = int(result[name], base)
                self.parsers.append(parse_end_time)
            elif re.search('resulttype', name):
                def parse_result_type(result, name = name):
                    self.result_type = result[name]
                self.parsers.append(parse_result_type)
            elif re.search('output', name):
                def parse_output(result, name = name):
                    self.output = result[name]
                self.parsers.append(parse_output)

    def classify(self):
        """
        Get result constant corresponding to the experiment result.
        """

        if self.result_type == "DONE":
            return Result.OK

        elif re.search("DOUBLE FAULT", self.output):
            return Result.DOUBLE_FAULT
        elif re.search("General Protection", self.output):
            return Result.GENERAL_PROTECTION_FAULT
        elif re.search("L4Re.*page fault", self.output):
            return Result.USER_ERROR
        elif re.search("L4Re.*unhandled exception", self.output):
            return Result.USER_ERROR
        elif re.search("MOE.*rm", self.output):
            return Result.USER_ERROR
        elif re.search("Return reboots", self.output):
            return Result.DOUBLE_FAULT
        elif re.search("ASSERTION", self.output):
            return Result.ASSERT_FAILED
        elif re.search("src\/kern\/context.cpp:1283", self.output):
            return Result.ASSERT_FAILED
        elif re.search("src\/kern\/ia32\/thread-ia32.cpp:65", self.output):
            return Result.ASSERT_FAILED
        elif re.search("src\/kern\/ia32\/thread-ia32.cpp:136", self.output):
            return Result.ASSERT_FAILED
        elif re.search("src\/kern\/ia32\/mem_space-ia32.cpp:185", self.output):
            return Result.ASSERT_FAILED
        elif re.search("src/kern/mapdb.cpp:609", self.output):
            return Result.ASSERT_FAILED
        elif re.search("N_FAILED", self.output):
            return Result.ASSERT_FAILED
        elif re.search("Error: Item", self.output):
            return Result.WRONG

        elif self.result_type == "WRONG":
            return Result.WRONG
        else:
            return Result.OTHER_ERROR

    def parse(self, result):
        for parser in self.parsers:
            try: parser(result)
            except ValueError: continue

class Register(object):
    bits = 32
    count = 8

    EAX, EBX, ECX, EDX, ESP, EBP, ESI, EDI = range(count)

    @staticmethod
    def read(name):
        if name == 'EAX': return Register.EAX
        if name == 'EBX': return Register.EBX
        if name == 'ECX': return Register.ECX
        if name == 'EDX': return Register.EDX
        if name == 'ESP': return Register.ESP
        if name == 'EBP': return Register.EBP
        if name == 'ESI': return Register.ESI
        if name == 'EDI': return Register.EDI
        raise ValueError('Register.read: not a register name')

    @staticmethod
    def show(number):
        if number == Register.EAX: return 'EAX'
        if number == Register.EBX: return 'EBX'
        if number == Register.ECX: return 'ECX'
        if number == Register.EDX: return 'EDX'
        if number == Register.ESP: return 'ESP'
        if number == Register.EBP: return 'EBP'
        if number == Register.ESI: return 'ESI'
        if number == Register.EDI: return 'EDI'
        raise ValueError('Register.show: not a register number')

    @staticmethod
    def bit_position(result):
        if result.bit is not None and result.register is not None:
            return result.register * Register.bits + result.bit

class Memory(object):
    bits = 8

    @staticmethod
    def read(string, base):
        try:
            address = int(string, base)
        except (ValueError, TypeError):
            raise ValueError('Memory.read: not a memory address')
        if address < 0:
            return address + 0x100000000
        return address

    @staticmethod
    def show(address):
        return "0x{:X}".format(address)

    @staticmethod
    def bit_position(result):
        if result.bit is not None and result.address is not None:
            return result.address * Memory.bits + result.bit

def create_symbol_table(filename):
    """
    Return a dictionary of address to symbol mappings for the given file.

    Extract the symbols using the tool 'nm'.
    Ignore the type of the symbol.

    The filename should correspond to an C++ object file.
    """

    symbol_table = SortedDict()

    # use '-C' to demangle C++ names
    for line in check_output(['nm', '-C', filename], universal_newlines = True).strip().split('\n'):
        values = line.split(' ', 2) # [ 'address', 'symbol type', 'symbol name' ]

        try:
            address = Memory.read(values[0], 16) 
            name    = values[2]
        except (IndexError, ValueError): continue

        symbol_table[address] = name

    return symbol_table

def read_symbol_table(filename):
    """
    Read the dictionary of address to symbol mappings from the given file.

    Ignore the type of the symbol.

    The filename should correspond to a file
    containing the output of the 'nm' tool for an C++ object file.
    """

    symbol_table = SortedDict()

    try:
        with open(filename, 'rb') as symbol_file:
            for values in csv.reader(symbol_file, delimiter = ' '):
                # values : [ 'address', 'symbol type', 'symbol name' ]
                try:
                    address = Memory.read(values[0], 16) 
                    name    = ' '.join(values[2:])
                except (IndexError, ValueError): continue

                symbol_table[address] = name
    except IOError: pass

    return symbol_table

def create_time_labels(trace, symbol_table):
    """
    Return a list of time-label-pairs.

    Arguments:
      trace - list of time-instruction pointer-pairs
      symbol_table - dictionary of address-symbol-mappings

    Process the trace in the order of the times.
    Foreach instruction pointer in the trace:
      Lookup the symbol with the biggest address 
      less than or equal to the instruction pointer.
      If the symbol is not the same as for the previous instruction pointer:
        Append the time and symbol to the final list.
    """

    # final list of time-label-pairs
    labels = []

    # sorted list of all addresses in the symbol table
    symbol_addresses = list(symbol_table)

    last_symbol = None
    for time, instruction_pointer in trace.items():
        try:
            # the biggest address smaller or equal to the instruction pointer
            address = symbol_addresses[bisect(symbol_addresses, instruction_pointer) - 1]
            # lookup the corresponding symbol and extract the function name
            symbol = symbol_table[address].split('(')[0]

            # only add a label if the symbol changed
            if symbol != last_symbol:
                labels.append((time, symbol))
                last_symbol = symbol
        except IndexError: pass # ignore instruction pointer with no corresponding symbol

    return labels

def parse_results(filename, data_class):
    data = SortedDict()
    trace = SortedDict()
    line_number = 0

    with open(filename, encoding = 'utf8', errors = 'ignore') as result_file:
        reader = csv.DictReader(result_file)
        result = Result(reader.fieldnames)
        for line in reader:
            result.parse(line)
            bit_position = data_class.bit_position(result)

            try: trace[result.end_time - 1] = result.instruction_pointer
            except AttributeError: pass

            try:
                data.setdefault(bit_position, SortedDict())
                data[bit_position][result.start_time - 1, result.end_time] = result.classify()
            except AttributeError: pass

    return data, trace

def create_register_labels():
    labels = SortedDict()

    for register in range(Register.count):
        position = Interval(register * Register.bits, Register.bits, True)
        labels[position] = Grouping(Register.show(register))

    return labels

def parse_memory_usage_data(file_name):
    memory_usage = []
    try:
        with open(file_name) as usage_file:
            for line in csv.reader(usage_file, delimiter = ' '):
                try:
                    address = Memory.read(line[0], 16)
                    size = int(line[1])
                    name = line[2]
                except (IndexError, ValueError): continue
                position = Interval(address * Memory.bits, size * Memory.bits, True)
                memory_usage.append((position, name))
    except (IOError, TypeError): pass
    return sorted(memory_usage)

def parse_structures(file_name):
    try:
        with open(file_name) as structures_file:
            content = structures_file.read()
    except (IOError, TypeError): content = ''
    return parse_structures_recursive(content)

def generate_clusters(positions):
    if not positions: raise StopIteration

    maximal_distance = 8
    
    lower = next(positions)
    upper = lower + 1
    for position in positions:
        if position - upper >= maximal_distance:
            yield Interval(lower, upper)
            lower = position
            upper = lower + 1
        else: upper = position + 1
    yield Interval(lower, upper)

def create_memory_labels(clusters, memory_usage = None, structures = None):
    shift = int(math.log2(Memory.bits))
    groups = SortedDict()

    def create_group(interval, parent = None, parent_interval = None):
        assert isinstance(interval, Interval)
        assert parent is None or isinstance(parent, Grouping)

        if parent_interval is not None:
            assert isinstance(parent_interval, Interval)
            offsets = map(lambda value: value - parent_interval.lower, interval)
            labels = tuple(map(lambda offset: '+ 0x{:X}'.format(offset >> shift), offsets))
        else:
            labels = tuple(map(lambda value: Memory.show(value >> shift), interval))
        groups[interval] = Grouping(*labels, parent = parent)

    def create_structure_labels(structure, position, cluster, parent = None):
        description = structure.description()
        if type(structure) is Substructure: structure = structure.structure.structure
        else: assert isinstance(structure, Structure)
        assert not structure.possible_size_known or structure.size * Memory.bits == position.length
        parent = Grouping(description, parent = parent)

        if isinstance(structure, Data):
            if isinstance(structure, DataUnion):
                parent = Choice(*parent)
                nonlocal clusters, groups
                original_cluster = cluster
                supergroups = groups
                cluster_list = []

                while cluster is not None and cluster.upper <= position.upper:
                    create_group(cluster, parent, position)
                    cluster_list.append(cluster)
                    cluster = next(clusters, None)
                if cluster is not None and cluster.lower < position.upper:
                    interval = Interval(cluster.lower, position.upper)
                    create_group(interval, parent, position)
                    cluster_list.append(interval)
                    cluster = Interval(position.upper, cluster.upper)

                parent.add_subgroup(groups)
                supergroups.update(groups)
                remaining_clusters = clusters

                for substructure in structure.substructures.items():
                    clusters = iter(cluster_list)
                    groups = SortedDict()
                    create_structure_labels(substructure, position, original_cluster, parent)
                    parent.add_subgroup(groups)

                groups = supergroups
                return cluster

            parent_position = position
            for offset, substructure in structure.substructures.items():
                assert offset == substructure.offset
                lower = parent_position.lower + substructure.offset * Memory.bits
                if not substructure.possible_size_known:
                    substructure.add_possible_size(parent_position.upper - lower)
                upper = lower + substructure.size * Memory.bits
                position = Interval(lower, upper)
                while cluster is not None and cluster.upper <= position.lower:
                    create_group(cluster, parent, parent_position)
                    cluster = next(clusters, None)
                if cluster is None: return
                if cluster.lower < position.lower:
                    create_group(Interval(cluster.lower, position.lower), parent, parent_position)
                    cluster = Interval(position.lower, cluster.upper)
                cluster = create_structure_labels(substructure, position, cluster, parent)
            position = parent_position

        while cluster is not None and cluster.upper <= position.upper:
            create_group(cluster, parent, position)
            cluster = next(clusters, None)
        if cluster is None: return cluster
        if cluster.lower < position.upper:
            create_group(Interval(cluster.lower, position.upper), parent, position)
            cluster = Interval(position.upper, cluster.upper)
        return cluster

    cluster = next(clusters, None)
    for position, name in memory_usage:
        while cluster is not None and cluster.upper <= position.lower:
            create_group(cluster)
            cluster = next(clusters, None)
        if cluster is None: break

        if cluster.lower < position.lower:
            create_group(Interval(cluster.lower, position.lower))
            cluster = Interval(position.lower, cluster.upper)

        if cluster.lower >= position.upper: continue

        if name in structures: structure = structures[name]
        else: structure = Data(name, size = int(math.ceil(position.length / Memory.bits)))

        cluster = create_structure_labels(structure, position, cluster)

    while cluster is not None:
        create_group(cluster)
        cluster = next(clusters, None)

    return groups

def position_information(time_labels, position_labels, x, y):
    times, labels = zip(*time_labels)
    time_index = times.bisect(x)
    name = labels[time_index]
    
    interval_index = position_labels.bisect((y,y))
    intervals = position_labels.keys()
    interval = intervals[interval_index - 1]

    group = position_labels[interval]
    if interval.upper <= y:
        next_group = position_labels[intervals[interval_index]]
        generation_difference = group.generation - next_group.generation
        if generation_difference > 0:
            for _ in range(generation_difference):
                group = group.parent
        elif generation_difference < 0:
            for _ in range(- generation_difference):
                next_group = next_group.parent
        while group is not next_group:
            group = group.parent
            next_group = next_group.parent
            assert group is not None and next_group is not None

    groups = []
    while group.parent is not None:
        groups.append(group)
        group = group.parent
    groups.reverse()

    return ''

def parse_arguments():
    parser = ArgumentParser()
    parser.add_argument("-b", "--binary",
                        help = "object file of the tested code")
    parser.add_argument("-t", "--symbol-table",
                        help = "symbol table of the tested code")
    parser.add_argument("-u", "--memory-usage",
                        help = "file with information about the position of data structures in memory")
    parser.add_argument("-s", "--data-structures",
                        help = "file with information about the structure of data structures in memory")
    parser.add_argument("-d", "--data", required = True,
                        help = "csv file with the test results")
    parser.add_argument("-r", "--register", action = 'store_true',
                        help = "show visualisation for register instead of memory")
    return parser.parse_args()

def print_status(description, function, *arguments, **keyword_arguments):
    print(description, '...', end = ' ')
    stdout.flush()
    result = function(*arguments, **keyword_arguments)
    print('done')
    stdout.flush()
    return result

def main():
    arguments = parse_arguments()

    if arguments.register:
        data, trace = print_status('parse register test results',
                                    parse_results, arguments.data, Register)

        position_labels = print_status('create register labels',
                                        create_register_labels)

        mirror = False

    else:
        memory_usage = print_status('parse memory usage data',
                                     parse_memory_usage_data, arguments.memory_usage)

        structures = print_status('parse data structures',
                                   parse_structures, arguments.data_structures)

        data, trace = print_status('parse memory test results',
                                    parse_results, arguments.data, Memory)

        clusters = print_status('generate clusters',
                                 generate_clusters, iter(sorted(data.keys())))

        position_labels = print_status('create memory labels',
                                        create_memory_labels, clusters, memory_usage, structures)

        mirror = True

    time_labels = {}
    symbol_table = None

    if arguments.binary is not None:
        symbol_table = print_status('create symbol table',
                                     create_symbol_table, arguments.binary)

    if arguments.symbol_table is not None:
        symbol_table = print_status('read symbol table',
                                     read_symbol_table, arguments.symbol_table)

    if symbol_table is not None:
        time_labels = print_status('create time labels',
                                    create_time_labels, trace, symbol_table)

    color_map = {
        Result.OK:                       'green',
        Result.WRONG:                    'red',
        Result.ASSERT_FAILED:            'blue',
        Result.DOUBLE_FAULT:             'yellow',
        Result.GENERAL_PROTECTION_FAULT: 'purple',
        Result.USER_ERROR:               'brown',
        Result.OTHER_ERROR:              'orange'
    }

    explanation = {
        Result.OK:                       'correct',
        Result.WRONG:                    'silent data corruption',
        Result.ASSERT_FAILED:            'assertion failed',
        Result.DOUBLE_FAULT:             'double fault',
        Result.GENERAL_PROTECTION_FAULT: 'general protection fault',
        Result.USER_ERROR:               'user error',
        Result.OTHER_ERROR:              'other error'
    }

    root = Tk()

    visualisation = print_status('create visualisation frame',
                                  Visualisation, root, data, color_map, explanation, time_labels, position_labels, mirror)

    visualisation.mainframe.grid(column = 0, row = 0, sticky = 'nsew')

    root.columnconfigure( 0, weight = 1 )
    root.rowconfigure(    0, weight = 1 )
    root.mainloop()

if __name__ == "__main__": main()
