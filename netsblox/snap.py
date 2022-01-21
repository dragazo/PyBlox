import random
import math

from typing import Any, Union

def _numerify(val: Any) -> Union[int, float]:
    vf = float(val)
    vi = int(vf)
    return vi if vi == vf else vf

class Int(int):
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return wrap(int(self) == float(other))
        return wrap(int(self) == other)

    def __add__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__radd__(self)
        return wrap(int(self) + _numerify(other))
    def __radd__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) + self
        return wrap(_numerify(other) + int(self))

    def __sub__(self, other: Any) -> Any:
        return self + -wrap(other)
    def __rsub__(self, other: Any) -> Any:
        return wrap(other) + -self

    def __neg__(self) -> 'Int':
        return Int(-int(self))

class Float(float):
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str): return wrap(float(self) == float(other))
        return wrap(float(self) == other)

    def __bool__(self) -> bool:
        return self != 0 and not math.isnan(self)

    def __add__(self, other) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__radd__(self)
        return Float(float(self) + float(other))
    def __radd__(self, other) -> Any:
        if not is_wrapped(other): return wrap(other) + self
        return Float(float(other) + float(self))

    def __sub__(self, other: Any) -> Any:
        return self + -wrap(other)
    def __rsub__(self, other: Any) -> Any:
        return wrap(other) + -self

    def __neg__(self) -> 'Float':
        return Float(-float(self))

class Str(str):
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, int) or isinstance(other, float): return float(self) == other
        return str(self) == other

    def __add__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__radd__(self)
        return wrap(_numerify(self) + other)
    def __radd__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) + self
        return wrap(other + _numerify(self))

    def __sub__(self, other: Any) -> Any:
        return self + -wrap(other)
    def __rsub__(self, other: Any) -> Any:
        return wrap(other) + -self

    def __neg__(self) -> Union['Int', 'Float']:
        return wrap(-_numerify(self))

class List(list):
    def __add__(self, other: Any) -> 'List':
        other = wrap(other)
        if isinstance(other, List): return List(wrap(self[i]) + wrap(other[i]) for i in range(min(len(self), len(other))))
        else: return List(wrap(x) + other for x in self)
    def __radd__(self, other: Any) -> 'List':
        other = wrap(other)
        return List(other + x for x in self)

    def __sub__(self, other: Any) -> Any:
        return self + -wrap(other)
    def __rsub__(self, other: Any) -> Any:
        return wrap(other) + -self

    def __neg__(self) -> 'List':
        return List(-x for x in self)

    def __bool__(self) -> bool:
        return True

_wrappers = { int: Int, float: Float, str: Str, list: List, tuple: List, set: List, dict: lambda v: List(List(x) for x in v.items()) }
def wrap(value: Any) -> Any:
    '''
    Wraps a value in a new type which changes operators like `+`, `-`, `*`, `/`, etc. to act like they do in Snap!.
    If the value is already wrapped (see `is_wrapped`), does nothing and returns the value directly.
    '''
    return _wrappers.get(type(value), lambda v: v)(value)
def is_wrapped(value: Any) -> bool:
    '''
    Checks if the given value is already wrapped.
    '''
    return type(value) == type(wrap(value))

def rand(a: Any, b: Any) -> Union[Int, Float]:
    '''
    Returns a random number in the range `[a, b]`.

    If both `a` and `b` are integer-valued (including floats holding integer values), returns an integer.
    Otherwise, returns a float in the continuous range.
    '''
    a, b = float(a), float(b)
    if a == b: return wrap(a)
    if a > b: a, b = b, a

    ai, bi = int(a), int(b)
    if ai == a and bi == b:
        return wrap(random.randint(ai, bi))

    return wrap(a + random.random() * (b - a))

def lnot(value: Any) -> Any:
    value = wrap(value)
    return List(lnot(x) for x in value) if isinstance(value, List) else not value

if __name__ == '__main__':
    v = wrap('hello world') ; assert v is wrap(v) and isinstance(v, Str)
    v = wrap(1223847982) ; assert v is wrap(v) and isinstance(v, Int)
    v = wrap(1223847982.453) ; assert v is wrap(v) and isinstance(v, Float)
    v = wrap([1,4,2,5,43]) ; assert v is wrap(v) and isinstance(v, List)
    v = wrap((1,4,2,5,43)) ; assert v is wrap(v) and isinstance(v, List)
    v = wrap({1,3,2,54}) ; assert v is wrap(v) and isinstance(v, List)
    v = wrap({1:1,3:4,2:2,54:3}) ; assert v is wrap(v) and isinstance(v, List)
    assert all(isinstance(x, List) and len(x) == 2 for x in v)
    assert v[1][0] == 3 and v[1][1] == 4 and v[-1][0] == 54 and v[-1][-1] == 3

    assert rand(5, 5) == 5 and rand(5.5, 5.5) == 5.5
    assert rand(5, '5') == wrap(5) and is_wrapped(rand(5, '5')) and is_wrapped(rand(wrap(7), '5')) and is_wrapped(rand(5.4, '5'))
    for _ in range(10): assert rand(5, 10) % 1 == 0 and rand(5, 10.0) % 1 == 0 and rand(5.0, 10) % 1 == 0 and rand(5.0, 10.0) % 1 == 0
    assert sum(rand(5.0, 10.1) % 1 for _ in range(10)) != 0 and sum(rand(5.1, 10) % 1 for _ in range(10)) != 0
    assert sum(rand(5.1, 10.0) % 1 for _ in range(10)) != 0 and sum(rand(5.1, 10.6) % 1 for _ in range(10)) != 0
    for _ in range(10): assert 5 <= rand(5, 10) <= 10 and 5 <= rand(10, 5) <= 10
    for _ in range(10): assert -5.5 <= rand(7, -5.5) <= 7 and -5.5 <= rand(-1, -5.5) <= -1

    assert not bool(wrap(None))
    assert bool(wrap(True)) and not bool(wrap(False))
    assert bool(wrap([])) and bool(wrap([0])) and bool(wrap([1])) and bool(wrap([1, 5]))
    assert bool(wrap(set())) and bool(wrap({0})) and bool(wrap({4, 0})) and bool(wrap({4: 4})) and bool(wrap({4: 4, 0: 0}))
    assert not bool(wrap('')) and bool(wrap('hello')) and bool(wrap('7')) and bool(wrap('0')) and bool(wrap('nan'))
    assert bool(wrap(7)) and bool(wrap(7.6)) and bool(wrap(-7.6)) and bool(wrap(7)) and bool(wrap(7.6)) and bool(wrap(-7.6))
    assert not bool(wrap(0)) and not bool(wrap(0.0)) and not bool(wrap(-0.0)) and not bool(wrap(math.nan))

    assert wrap([1,2,3]) + wrap([6,2,-2]) == [7,4,1] and wrap([1,2,3]) - wrap([6,2,-2]) == [-5,0,5] and wrap([1,2,3]) - wrap([6,2]) == [-5,0] and wrap([1]) - wrap([6,2]) == [-5]
    assert wrap([[1,5,2], [1,2], [0], []]) + wrap('4') == [[5,9,6], [5,6], [4], []] and wrap([[1,5,2], [1,2], [0], []]) + '4' == [[5,9,6], [5,6], [4], []]
    assert wrap([[1,5,2], [1,2], [0], []]) - wrap('2') == [[-1,3,0], [-1,0], [-2], []]
    assert wrap([[1,5,2], [1,2], [0], []]) - '2' == [[-1,3,0], [-1,0], [-2], []]
    assert wrap([1,2,3]) + 3 == [4,5,6] and wrap([1,2,3]) + wrap(3) == [4,5,6] and wrap([1,2,3]) + '3' == [4,5,6] and wrap([1,2,3]) + wrap('3') == [4,5,6]
    assert 5 + wrap([3,2,5]) == [8,7,10] and wrap(5) + wrap([3,2,5]) == [8,7,10] and '5' + wrap([3,2,5]) == [8,7,10] and wrap('5') + wrap([3,2,5]) == [8,7,10]
    assert wrap([4,7,2])[0] == 4 and wrap([4,7,2])[1] == 7 and len(wrap([4,7,2])) == 3

    assert wrap(3) == wrap('3') and wrap(3.0) == wrap('3') and wrap(3) == wrap('3.0') and wrap(3.0) == wrap('3.0')
    assert -wrap(3) == -wrap('3') and is_wrapped(-wrap(3)) and is_wrapped(-wrap('4'))
    assert not [] and wrap([]) and wrap(wrap([]))
    assert len(wrap([6,2,4])) == wrap('3')

    assert is_wrapped(wrap(3) + wrap(3)) and is_wrapped(wrap(3) - wrap(3)) and is_wrapped(3 - wrap(3)) and is_wrapped(wrap(3) - 3)
    assert 3 + wrap(3) == 6 and is_wrapped(3 + wrap(3)) and is_wrapped(wrap(3) - 3) and 3 - wrap(2) == 1 and is_wrapped(3 - wrap(2)) and is_wrapped(wrap(3) - 2)
    assert is_wrapped(wrap(3.75) + wrap(2.5)) and is_wrapped(wrap(3.75) - wrap(2.5)) and is_wrapped(wrap(3.75) - 2.5) and is_wrapped(3.75 - wrap(2.5))
    assert wrap(3.75) + wrap(2.5) == 6.25 and wrap(3.75) - wrap(2.5) == 1.25 and 3.75 - wrap(2.5) == 1.25 and wrap(3.75) - 2.5 == 1.25
    assert is_wrapped(wrap('3') + wrap('3')) and is_wrapped(wrap('3') - wrap('3')) and is_wrapped('3' - wrap('3')) and is_wrapped(wrap('3') - '3')
    assert wrap('3') + wrap('7') == 10 and wrap('3') + '7' == 10 and isinstance(wrap('3') + wrap('7'), Int) and isinstance(wrap('3') + '7', Int)

    print('passed all tests')
