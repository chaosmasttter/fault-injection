from collections import namedtuple

class Interval(namedtuple('Interval', ['lower', 'upper'])):
    def __new__(self_class, a, b, length_given = False):
        assert isinstance(a, int) and isinstance(b, int)
        assert isinstance(length_given, bool)
        assert length_given or a <= b

        if length_given: b += a
        return super(Interval, self_class).__new__(self_class, a, b)

    @property
    def length(self):
        assert self.lower <= self.upper
        return self.upper - self.lower

class Grouping(namedtuple('Grouping', ['header', 'footer', 'parent'])):
    def __new__(self_class, header = '', footer = '', parent = None, *arguments, **keyword_arguments):
        self = super(Grouping, self_class).__new__(self_class, header, footer, parent)
        self.initialise(*arguments, **keyword_arguments)
        return self

    def initialise(self):
        self.seen = False

        if self.parent is None: self.depth = 0
        else:                   self.depth = self.parent.depth + 1 

class Choice(Grouping):
    def initialise(self, subgroups = []):
        super().initialise()
        self.subgroupings = subgroupings
        self.choice = 0

    def add_subgroup(self, subgroup):
        self.subgroups.append(subgroup)

    def choose(self, index):
        self.choice = index
        return self.subgroupings[index]
