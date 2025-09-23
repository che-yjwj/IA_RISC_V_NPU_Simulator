import numpy as np


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
    dividend = np.int32(a).item()
    divisor = np.int32(b).item()
    if divisor == 0:
        return -1
    if dividend == -0x80000000 and divisor == -1:
        return -0x80000000
    negative = (dividend < 0) ^ (divisor < 0)
    quotient = abs(dividend) // abs(divisor)
    return -quotient if negative else quotient
