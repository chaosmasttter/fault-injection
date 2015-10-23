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

from graphicalInterface import Visualisation
from structures import parse_structures_recursive, allows_choice
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

    symbol_table = {}

    # use '-C' to demangle C++ names
    for line in check_output(['nm', '-C', filename]).strip().split('\n'):
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

    symbol_table = {}

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
    symbol_addresses = sorted(symbol_table)

    last_symbol = None
    for time, instruction_pointer in sorted(trace):
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

    with open(filename, 'r') as result_file:
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
    labels = {}

    for register in range(Register.count):
        lower = register * Register.bits
        upper = lower + Register.bits
        labels[lower, upper] = Group(Register.show(register), group = Interval(lower, upper))

    return labels

def parse_memory_usage_data(file_name):
    memory_usage = []
    try:
        with open(file_name, 'r') as usage_file:
            for line in csv.reader(usage_file, delimiter = ' '):
                try:
                    address = Memory.read(line[0], 16)
                    size = int(line[1])
                    name = line[2]
                except (IndexError, ValueError): continue
                position = Interval(address * Memory.bits, size * Memory.bits, True)
                memory_usage.append((position, name))
    except (IOError, TypeError): pass
    return sorted(memory_usage, reverse = True)

def parse_structures(file_name):
    try:
        with open(file_name, 'r') as structures_file:
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
    groups = SortedDict()
    
    def create_group(interval, parent = None):
        labels = tuple(map(lambda value: Memory.show(value >> int(math.log2(Memory.bits))), interval))
        groups[interval] = Grouping(*labels, parent, interval)

    cluster = next(clusters, None)
    for position, name in memory_usage:
        while cluster is not None and cluster.upper <= position.lower:
            create_group(cluster)
            cluster = next(clusters, None)
        if cluster is None: break

        if cluster.lower < position.lower:
            create_group(Interval(cluster.lower, position.lower))
            cluster = Interval(position.lower, cluster.upper)

        if name in structures:
            structure = structures[name]
            assert structure.presize.no_estimate_possible or structure.size == position.length
            parent = Grouping(structure.description())
            
            if isinstance(structure, Data):
                parents = []

            else:
                while cluster is not None and cluster.upper <= position.upper:
                    create_group(cluster, parent)
                    cluster = next(clusters, None)
                if cluster.lower < position.upper:
                    create_group(Interval(cluster.lower, position.upper), parent)
                    cluster = Interval(position.upper, cluster.upper)

     while cluster is not None:
         create_group(cluster)
         cluster = next(clusters, None)

     return groups

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

    root = Tk()

    if arguments.register:
        data, trace = print_status('parse register test results',
                                    parse_results, arguments.data, Register)

        position_labels = print_status('create register labels',
                                        create_register_labels)

    else:
        data, trace = print_status('parse memory test results',
                                    parse_results, arguments.data, Memory)

        memory_usage = print_status('parse memory usage data',
                                     parse_memory_usage_data, arguments.memory_usage)

        structures = print_status('parse data structures',
                                  parse_structures, arguments.data_structures)

        for name, structure in structures.items():
            print(name, structure)

        clusters = print_status('generate clusters',
                                generate_clusters, iter(sorted(data.keys())))

        position_labels = print_status('create memory labels',
                                        create_memory_labels, clusters, memory_usage, structures)

        for interval, group in position_labels.items():
            print(interval, group)

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

    visualisation = print_status('create visualisation frame',
                                  Visualisation, root, data, color_map, explanation, time_labels, position_labels)

    visualisation.mainframe.grid(column = 0, row = 0, sticky = 'nsew')

    root.columnconfigure( 0, weight = 1 )
    root.rowconfigure(    0, weight = 1 )
    root.mainloop()

if __name__ == "__main__": main()
