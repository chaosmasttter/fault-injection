from collections import namedtuple

class Grouping(namedtuple('Grouping', ['header', 'footer', 'parent'])):
    def __new__(self_class, header = '', footer = '', parent = None, *arguments, **keyword_arguments):
        self = super(Grouping, self_class).__new__(self_class, header, footer, parent)
        self.initialise(*arguments, **keyword_arguments)
        return self

    def initialise(self): pass

class Group(Grouping):
    def initialise(self, group):
        self.group = group

class Choice(Group):
    def initialise(self, group, subgroupings = {}):
        super(Choice, self).initialise(group)
        self.subgroupings = subgroupings
        self.choice = None

    def choices(self):
        return self.subgroupings.keys()

    def choose(self, key):
        self.choice = key
        return self.subgroupings[key]
