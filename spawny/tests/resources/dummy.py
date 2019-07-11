from collections import OrderedDict

i = 1

odct = OrderedDict()
odct['a'] = 1


foo_str = "hello world"


class Foo(object):
    def __init__(self, i):
        self.i = 1

    def say_hello(self, who):
        return "[Foo-%s] hello, %s!" % (self.i, who)

    def __eq__(self, other):
        return self.i == other.i


foo = Foo(1)


def say_hello(who):
    return "hello, %s!" % who


print(foo.say_hello("process"))
print(say_hello("process"))
