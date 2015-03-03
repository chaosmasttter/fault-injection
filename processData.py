#!/usr/bin/env python

import re
import csv
import sys
from itertools import chain
from struct import unpack
from subprocess import check_output
from argparse import ArgumentParser
from Tkinter import Tk
from graphicalInterface import Visualisation

class ResultType:
    OK, \
    WRONG, \
    ASSERT_FAILED, \
    DOUBLE_FAULT, \
    GENERAL_PROTECTION_FAULT, \
    USER_ERROR, \
    OTHER_ERROR = range(7)

    @staticmethod
    def classify(result):
        resultType = result['resulttype']
        output     = result['output']

        if resultType == "DONE":
            return ResultType.OK

        if re.search("DOUBLE FAULT", output):
            return ResultType.DOUBLE_FAULT
        elif re.search("General Protection", output):
            return ResultType.GENERAL_PROTECTION_FAULT
        elif re.search("L4Re.*page fault", output):
            return ResultType.USER_ERROR
        elif re.search("L4Re.*unhandled exception", output):
            return ResultType.USER_ERROR
        elif re.search("MOE.*rm", output):
            return ResultType.USER_ERROR
        elif re.search("Return reboots", output):
            return ResultType.DOUBLE_FAULT
        elif re.search("ASSERTION", output):
            return ResultType.ASSERT_FAILED
        elif re.search("src\/kern\/context.cpp:1283", output):
            return ResultType.ASSERT_FAILED
        elif re.search("src\/kern\/ia32\/thread-ia32.cpp:65", output):
            return ResultType.ASSERT_FAILED
        elif re.search("src\/kern\/ia32\/thread-ia32.cpp:136", output):
            return ResultType.ASSERT_FAILED
        elif re.search("src\/kern\/ia32\/mem_space-ia32.cpp:185", output):
            return ResultType.ASSERT_FAILED
        elif re.search("src/kern/mapdb.cpp:609", output):
            return ResultType.ASSERT_FAILED
        elif re.search("N_FAILED", output):
            return ResultType.ASSERT_FAILED
        elif re.search("Error: Item", output):
            return ResultType.WRONG # that's a (detected) SDC actually...

        elif resultType == "WRONG":
            return ResultType.WRONG
        else:
            return ResultType.OTHER_ERROR

class Register(object):
    descriptor = 'register_offset'
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

class Memory(object):
    descriptor = 'HEX(res.injection_address)'
    bits = 8

    @staticmethod
    def read(string):
        try:
            address = long(string, 16)
        except (ValueError, TypeError):
            raise ValueError('Memory.read: not a memory address')
        if address < 0:
            return address + 0x100000000
        return address

    @staticmethod
    def show(address):
        return "0x{:X}".format(address)

def createSymbolTable(filename):
    symbolTable = {}

    for line in check_output(['nm', '-C', filename]).strip().split('\n'):
        values = line.split(' ', 2)

        try:
            address = int(values[0], 16)
            name    = values[2]
        except (IndexError, ValueError): continue

        symbolTable[address] = name

    return symbolTable

def processInstructionPointerTrace(filename, symbolTable):
    functions = []

    with open(filename, 'rb') as traceFile:
        lastFunction = ''
        time = 0

        for traceEntry in iter(lambda:traceFile.read(16), ''):
            if len(traceEntry) < 16: break

            time += 1
            instructionPointer, _ = unpack('LL', traceEntry)
            try:
                function = symbolTable[instructionPointer].split('(')[0]
            except KeyError: continue
            if function != lastFunction:
                functions.append((time, function))

    return functions

def parseResults(filename, classify, dataClass):
    data = {}

    with open(filename, 'rU') as resultFile:
        for result in csv.DictReader(resultFile):
            try:
                position = dataClass.read(result[dataClass.descriptor])
                bit      = int(result['bit_offset'])

                timeStart = int(result['time1'])
                timeEnd   = int(result['time2']) + 1
            except (KeyError, ValueError): continue

            bitPosition = position * dataClass.bits + bit
            value       = classify(result)

            if bitPosition not in data:
                data[bitPosition] = {}
            data[bitPosition][timeStart, timeEnd] = value

    return data

def createRegisterLabels():
    labels = []

    for register in range(Register.count):
        lower = register * Register.bits
        upper = lower + Register.bits
        labels.append(((Register.show(register), ''), [((lower, upper), [])]))

    return labels

def createMemoryLabels(data, usage, structures):
    memoryUsage = []
    if usage is not None:
        with open(usage, 'rU') as usageFile:
            for line in csv.reader(usageFile, delimiter = ' '):
                try:
                    address = Memory.read(line[0])
                    size = int(line[1])
                    name = line[2]
                except (IndexError, ValueError): continue
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
                dataStructures[structureName] = structure

    labels = []
    maximalDistance = 8 * 8

    cluster = []
    lastClusterEnd = None

    for position in sorted(data.keys()):
        if lastClusterEnd is None or lastClusterEnd + maximalDistance < position:
            cluster.append((position, position))
            lastClusterEnd = position
        else:
            cluster[-1] = cluster[-1][0], position

    clusterIterator = iter(cluster)
    for (start, end), name in sorted(memoryUsage):
        structureCluster = []
        for lower, upper in clusterIterator:
            if lower >= end:
                clusterIterator = chain([(lower, upper)], clusterIterator)
                break
            elif upper <= start:
                lowerLabel = Memory.show(lower >> 3)
                upperLabel = Memory.show(lower >> 3)
                labels.append(((lowerLabel, upperLabel), [((lower, upper), [])]))
            elif lower < start:
                newCluster = [(lower, start), (start, upper)]
                clusterIterator = chain(newCluster, clusterIterator)
            elif upper > end:
                newCluster = [(lower, end), (end, upper)]
                clusterIterator = chain(newCluster, clusterIterator)
            else:
                structureCluster.append((lower, upper))
        if structureCluster == []: continue

        outer = []
        try:
            fieldIterator = iter(sorted(dataStructures[name]))
            for lower, upper in structureCluster:
                lastField = None
                inner = []
                for offset, field in fieldIterator:
                    position = start + offset * Memory.bits
                    if position < lower:
                        lastField = position, field 
                    elif position < upper:
                        inner.append((position, field))
                    else: break
                if lastField is not None:
                    position, field = lastField
                    outer.append(((position, position), [(position, field)]))
                outer.append(((lower, upper), inner))
        except KeyError:
            for cluster in structureCluster:
                outer.append((cluster, []))
        labels.append(((name, ''), outer))

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
    trace  = arguments.trace
    
    root = Tk()

    timeLabels = {}
    if binary is not None and trace is not None:
        printStatus("Create symbol table ...")
        symbolTable = createSymbolTable(arguments.binary)
        printStatus("Done")

        printStatus("Process instruction pointer trace ...")
        timeLabels = processInstructionPointerTrace(arguments.trace, symbolTable)
        printStatus("Done")

    if arguments.register:
        printStatus("Parse register test results ...")
        data = parseResults(arguments.data, ResultType.classify, Register)
        printStatus("Done")

        printStatus("Create register labels ...")
        positionLabels = createRegisterLabels()
        printStatus("Done")

    else:
        printStatus("Parse memory test results ...")
        data = parseResults(arguments.data, ResultType.classify, Memory)
        printStatus("Done")

        printStatus("Create memory labels ...")
        positionLabels = createMemoryLabels(data, arguments.memory_usage, arguments.data_structures)
        printStatus("Done")

    colorMap = {
        ResultType.OK:                       'green',
        ResultType.WRONG:                    'red',
        ResultType.ASSERT_FAILED:            'blue',
        ResultType.DOUBLE_FAULT:             'yellow',
        ResultType.GENERAL_PROTECTION_FAULT: 'purple',
        ResultType.USER_ERROR:               'darkgreen',
        ResultType.OTHER_ERROR:              'orange'
    }

    explanation = {
        ResultType.OK:                       'correct',
        ResultType.WRONG:                    'silent data corruption',
        ResultType.ASSERT_FAILED:            'assertion failed',
        ResultType.DOUBLE_FAULT:             'double fault',
        ResultType.GENERAL_PROTECTION_FAULT: 'general protection fault',
        ResultType.USER_ERROR:               'user error',
        ResultType.OTHER_ERROR:              'other error'
    }

    printStatus("Create visualisation frame ...")
    Visualisation(root, data, colorMap, explanation, timeLabels, positionLabels
                 ).mainframe.grid(column = 0, row = 0, sticky = 'nsew')
    printStatus("Done")
    
    root.columnconfigure( 0, weight = 1 )
    root.rowconfigure(    0, weight = 1 )
    root.mainloop()

if __name__ == "__main__": main()
