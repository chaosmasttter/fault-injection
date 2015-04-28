#!/usr/bin/env python

import re
import csv
import sys
from bisect import bisect
from decimal import Decimal
from struct import unpack
from subprocess import check_output
from argparse import ArgumentParser
from Tkinter import Tk
from graphicalInterface import Visualisation

class Result:
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

    bit = None
    register = None
    address = None
    instructionPointer = None
    timeStart = None
    timeEnd = None
    resultType = None
    output = None

    def __init__(self, names):
        self.parsers = []

        for name in names:
            if re.search('HEX', name): base = 16
            else: base = 10

            if re.search('bit_offset', name):
                def parseBit(result, name = name, base = base):
                    self.bit = int(result[name], base)
                self.parsers.append(parseBit)
            elif re.search('register_offset', name):
                def parseRegister(result, name = name):
                    self.register = Register.read(result[name])
                self.parsers.append(parseRegister)
            elif re.search('injection_address', name):
                def parseAddress(result, name = name, base = base):
                    self.address = Memory.read(result[name], base)
                self.parsers.append(parseAddress)
            elif re.search('injection_ip', name):
                def parseInstructionPointer(result, name = name, base = base):
                    self.instructionPointer = Memory.read(result[name], base)
                self.parsers.append(parseInstructionPointer)
            elif re.search('time1', name):
                def parseStartTime(result, name = name, base = base):
                    self.startTime = int(result[name], base)
                self.parsers.append(parseStartTime)
            elif re.search('time2', name):
                def parseEndTime(result, name = name, base = base):
                    self.endTime = int(result[name], base)
                self.parsers.append(parseEndTime)
            elif re.search('resulttype', name):
                def parseResultType(result, name = name):
                    self.resultType = result[name]
                self.parsers.append(parseResultType)
            elif re.search('output', name):
                def parseOutput(result, name = name):
                    self.output = result[name]
                self.parsers.append(parseOutput)

    def classify(self):
        """
        Get result constant corresponding to the experiment result.
        """

        if self.resultType == "DONE":
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

        elif self.resultType == "WRONG":
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
    def bitPosition(result):
        if result.bit is not None and result.register is not None:
            return result.register * Register.bits + result.bit

class Memory(object):
    bits = 8

    @staticmethod
    def read(string, base):
        try:
            address = long(string, base)
        except (ValueError, TypeError):
            raise ValueError('Memory.read: not a memory address')
        if address < 0:
            return address + 0x100000000
        return address

    @staticmethod
    def show(address):
        return "0x{:X}".format(address)

    @staticmethod
    def bitPosition(result):
        if result.bit is not None and result.address is not None:
            return result.address * Memory.bits + result.bit

def createSymbolTable(filename):
    """
    Return a dictionary of address to symbol mappings for the given file.

    The filename should correspond to an C++ object file.

    Extract the symbols using the tool 'nm'.
    Ignore the type of the symbol.
    """

    symbolTable = {}

    # use '-C' to demangle C++ names
    for line in check_output(['nm', '-C', filename]).strip().split('\n'):
        values = line.split(' ', 2) # [ 'address', 'symbol type', 'symbol name' ]

        try:
            address = Memory.read(values[0], 16) 
            name    = values[2]
        except (IndexError, ValueError): continue

        symbolTable[address] = name

    return symbolTable

def createTimeLabels(trace, symbolTable):
    """
    Return a list of time-label-pairs.

    Arguments:
      trace - list of time-instruction pointer-pairs
      symbolTable - dictionary of address-symbol-mappings

    Process the trace in the order of the times.
    Foreach instruction pointer in the trace:
      Lookup the symbol with the biggest address 
      smaller or equal to the instruction pointer.
      If the symbol is not the same as for the previous instruction pointer:
        Append the time and symbol to the final list.
    """

    # final list of time-label-pairs
    labels = []

    # sorted list of all addresses in the symbol table
    symbolAddresses = sorted(symbolTable)

    lastSymbol = None
    for time, instructionPointer in sorted(trace):
        try:
            # the biggest address smaller or equal to the instruction pointer
            address = symbolAddresses[bisect(symbolAddresses, instructionPointer) - 1]
            # lookup the corresponding symbol and extract the function name
            symbol = symbolTable[address].split('(')[0]

            # only add a label if the symbol changed
            if symbol != lastSymbol:
                labels.append((time, symbol))
                lastSymbol = symbol
        except IndexError: pass

    return labels

def parseResults(filename, dataClass):
    data = {}
    trace = {}

    with open(filename, 'rU') as resultFile:
        reader = csv.DictReader(resultFile)
        result = Result(reader.fieldnames)
        for line in reader:
            result.parse(line)
            bitPosition = dataClass.bitPosition(result)

            if result.instructionPointer is not None and result.endTime is not None:
                trace[result.endTime] = result.instructionPointer

            if bitPosition is not None \
              and result.startTime is not None and result.endTime is not None:
                if bitPosition not in data:
                    data[bitPosition] = {}
                data[bitPosition][result.startTime - 1, result.endTime] = result.classify()

    return data, trace.items()

def createRegisterLabels():
    labels = []

    for register in range(Register.count):
        lower = register * Register.bits
        upper = lower + Register.bits
        labels.append((('', Register.show(register)), (lower, upper)))

    return labels

def createMemoryLabels(data, usage, structures):
    memoryUsage = []
    if usage is not None:
        with open(usage, 'rU') as usageFile:
            for line in csv.reader(usageFile, delimiter = ' '):
                try:
                    address = Memory.read(line[0], 16)
                    size = int(line[1])
                    name = line[2]
                except (IndexError, ValueError):
                    print 'unable to read'
                    continue
                position = address * Memory.bits, (address + size) * Memory.bits
                memoryUsage.append((position, name))

    def parse(line):
        depth = 0
        nextResult = []
        for char in line:
            if depth == 0 and char == ',':
                yield ''.join(nextResult).strip()
                nextResult = []
                continue

            if char == '<':
                depth += 1
            if char == '>':
                depth -= 1

            nextResult.append(char)
        yield ''.join(nextResult).strip()

    dataStructures = {}
    if structures is not None:
        with open(structures, "rU") as structureFile:
            for line in structureFile:
                fieldIterator = parse(line)
                try:
                    structureName = next(fieldIterator)
                    next(fieldIterator)
                except StopIteration: continue
                structure = []
                for name, offset in zip(* [fieldIterator] * 2):
                    structure.append((int(offset), name))
                if structure != []:
                    dataStructures[structureName] = structure

    maximalDistance = 8 * 8
    clusters = []

    for position in sorted(data.keys()):
        if clusters:
            lower, upper = cluster = clusters.pop()
            if position < upper + maximalDistance:
                clusters.append((lower, position))
                continue
            clusters.append(cluster)
        clusters.append((position, position))
    clusters.reverse()

    superlabels = []
    labels = []

    superstructures = []
    structures = sorted(memoryUsage, reverse = True)

    ends = [Decimal('Infinity')]

    while clusters or superstructures:
        if structures:
            lower, upper = cluster = clusters.pop()
            (start, end), name = structure = structures.pop()

            if lower < start:
                if upper > start:
                    clusters.append((start, upper))
                    cluster = lower, start

                if superstructures: label = '', ''
                else: label = Memory.show(lower >> 3), Memory.show(upper >> 3)
                labels.append((label, cluster))
                structures.append(structure)

            elif upper <= end:
                labels.append(('', name))
                superlabels.append(labels)
                labels = []

                superstructures.append(structures)
                structures = []

                ends.append(end)
                clusters.append(cluster)

                if name in dataStructures:
                    for offset, name in sorted(dataStructures[name], reverse = True):
                        position = start + Memory.bits * offset, end
                        structures.append((position, name))
                        end = position[0]

            elif lower < end:
                structures.append(structure)
                clusters.extend([(lower, end), (end, upper)])
            else: clusters.append(cluster)

        else:
            end = ends.pop()
            while clusters:
                cluster = clusters.pop()
                if end < cluster[1]:
                    clusters.append(cluster)
                    break
                if superstructures: label = '', ''
                else: label = Memory.show(lower >> 3), Memory.show(upper >> 3)
                labels.append((label, cluster))

            if superstructures:
                structures = superstructures.pop()

                sublabels = labels
                labels = superlabels.pop()
                label = labels.pop()
                labels.append((label, sublabels))
            else: break

    return labels

def parseArguments():
    parser = ArgumentParser()
    parser.add_argument("-b", "--binary",
                        help = "object file of the tested code")
    parser.add_argument("-t", "--trace",
                        help = "trace of the instruction pointer")
    parser.add_argument("-u", "--memory-usage",
                        help = "file with information about the position of data structures in memory")
    parser.add_argument("-s", "--data-structures",
                        help = "file with information about the structure of data structures in memory")
    parser.add_argument("-d", "--data", required = True,
                        help = "csv file with the test results")
    parser.add_argument("-r", "--register", action = 'store_true',
                        help = "show visualisation for register instead of memory")
    return parser.parse_args()

def printStatus(status):
    print status,
    if status == "Done": print

    sys.stdout.flush()

def main():
    arguments = parseArguments()
    binary = arguments.binary
    
    root = Tk()

    timeLabels = {}
    if arguments.register:
        printStatus("Parse register test results ...")
        data, trace = parseResults(arguments.data, Register)
        printStatus("Done")

        printStatus("Create register labels ...")
        positionLabels = createRegisterLabels()
        printStatus("Done")

    else:
        printStatus("Parse memory test results ...")
        data, trace = parseResults(arguments.data, Memory)
        printStatus("Done")

        printStatus("Create memory labels ...")
        positionLabels = createMemoryLabels(data, arguments.memory_usage, arguments.data_structures)
        printStatus("Done")

    if binary is not None:
        printStatus("Create symbol table ...")
        symbolTable = createSymbolTable(binary)
        printStatus("Done")

        printStatus("Create time labels ...")
        timeLabels = createTimeLabels(trace, symbolTable)
        printStatus("Done")

    colorMap = {
        Result.OK:                       'green',
        Result.WRONG:                    'red',
        Result.ASSERT_FAILED:            'blue',
        Result.DOUBLE_FAULT:             'yellow',
        Result.GENERAL_PROTECTION_FAULT: 'purple',
        Result.USER_ERROR:               'darkgreen',
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

    printStatus("Create visualisation frame ...")
    Visualisation(root, data, colorMap, explanation, timeLabels, positionLabels
                 ).mainframe.grid(column = 0, row = 0, sticky = 'nsew')
    printStatus("Done")
    
    root.columnconfigure( 0, weight = 1 )
    root.rowconfigure(    0, weight = 1 )
    root.mainloop()

if __name__ == "__main__": main()
