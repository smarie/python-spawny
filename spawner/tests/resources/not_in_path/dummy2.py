from collections import OrderedDict

odct = OrderedDict()
odct['a'] = 1

foo = "hello world"

def say_hello(who):
    return "hello, %s!" % who

print(say_hello("process"))
