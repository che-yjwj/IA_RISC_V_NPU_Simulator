def add(a, b):
    return a + b

def sub(a, b):
    return a - b

def and_(a, b):
    return a & b

def or_(a, b):
    return a | b

def xor(a, b):
    return a ^ b

def fmadd(a, b, c):
    return a * b + c


def mul(a, b):
    return a * b


def div(a, b):
    if b == 0:
        return -1
    return int(a // b)
