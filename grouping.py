from collections import namedtuple

class Interval(namedtuple('Interval', ['lower', 'upper'])):
   def __new__(self_class, a, b, length_given = False):
       if length_given: b += a
       return super(Interval, self_class).__new__(self_class, a, b)

class Grouping(namedtuple('Grouping', ['header', 'footer', 'parent'])):
    def __new__(self_class, header = '', footer = '', parent = None, *arguments, **keyword_arguments):
        self = super(Grouping, self_class).__new__(self_class, header, footer, parent)
        self.initialise(*arguments, **keyword_arguments)
        return self

    def initialise(self, group = None):
        self.group(group)

    def group(self, group):
        if isinstance(group, Interval): self.group = group

class Choice(Grouping):
    def initialise(self, group, subgroupings = {}):
        super(Choice, self).initialise(group)
        self.subgroupings = subgroupings
        self.choice = None

    def choices(self):
        return self.subgroupings.keys()

    def choose(self, key):
        self.choice = key
        return self.subgroupings[key]
