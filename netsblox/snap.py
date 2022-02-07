import random
import math

from typing import Any, Union, Callable

def _numerify(val: Any) -> Union[int, float]:
    vf = float(val)
    vi = int(vf)
    return vi if vi == vf else vf

def _is_matrix(v: Any) -> bool:
    return isinstance(v, list) and len(v) > 0 and isinstance(list.__getitem__(v, 0), list)
def _is_list(v: Any) -> bool:
    return isinstance(v, list)

def _list_op(a: Any, b: Any, op: Callable, matrix_mode: bool = True) -> 'List':
    assert is_wrapped(a) and is_wrapped(b)
    checker = _is_matrix if matrix_mode else _is_list
    if checker(a):
        if checker(b):
            return List(_list_op(wrap(list.__getitem__(a, i)), wrap(list.__getitem__(b, i)), op, matrix_mode) for i in range(min(len(a), len(b))))
        return List(_list_op(wrap(list.__getitem__(a, i)), b, op, matrix_mode) for i in range(len(a)))
    if checker(b):
        return List(_list_op(a, wrap(list.__getitem__(b, i)), op, matrix_mode) for i in range(len(b)))
    return _list_op(a, b, op, False) if matrix_mode else op(a, b)

def _scalar_op(a: Any, b: Any, op: Callable) -> 'Float':
    a, b = float(a), float(b)
    try:
        return Float(op(a, b))
    except OverflowError:
        return Float(math.inf)

class Float(float):
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str): return wrap(float(self) == float(other))
        return wrap(float(self) == other)

    def __bool__(self) -> bool:
        return self != 0 and not math.isnan(self)

    def __add__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__radd__(self)
        return _scalar_op(self, other, lambda a, b: a + b)
    def __radd__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) + self
        return _scalar_op(other, self, lambda a, b: a + b)

    def __sub__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__rsub__(self)
        return _scalar_op(self, other, lambda a, b: a - b)
    def __rsub__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) - self
        return _scalar_op(other, self, lambda a, b: a - b)

    def __mul__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__rmul__(self)
        return _scalar_op(self, other, lambda a, b: a * b)
    def __rmul__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) * self
        return _scalar_op(other, self, lambda a, b: a * b)

    def __truediv__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__rtruediv__(self)
        return _scalar_op(self, other, lambda a, b: a / b)
    def __rtruediv__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) / self
        return _scalar_op(other, self, lambda a, b: a / b)

    def __floordiv__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__rfloordiv__(self)
        return _scalar_op(self, other, lambda a, b: a // b)
    def __rfloordiv__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) // self
        return _scalar_op(other, self, lambda a, b: a // b)

    def __pow__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__rpow__(self)
        return _scalar_op(self, other, lambda a, b: a ** b)
    def __rpow__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) ** self
        return _scalar_op(other, self, lambda a, b: a ** b)

    def __neg__(self) -> 'Float':
        return Float(-float(self))

class Str(str):
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, int) or isinstance(other, float): return float(self) == other
        return str(self) == other

    def __add__(self, other: Any) -> Any:
        return Float(self) + other
    def __radd__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) + self
        return wrap(other + float(self))

    def __sub__(self, other: Any) -> Any:
        return Float(self) - other
    def __rsub__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) - self
        return wrap(other - float(self))

    def __mul__(self, other: Any) -> Any:
        return Float(self) * wrap(other)
    def __rmul__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) * self
        return wrap(other * float(self))

    def __truediv__(self, other: Any) -> Any:
        return Float(self) / wrap(other)
    def __rtruediv__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) / self
        return wrap(other / float(self))

    def __floordiv__(self, other: Any) -> Any:
        return Float(self) // wrap(other)
    def __rfloordiv__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) // self
        return wrap(other // float(self))

    def __pow__(self, other: Any) -> Any:
        return Float(self) ** wrap(other)
    def __rpow__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) ** self
        return wrap(other ** float(self))

    def __neg__(self) -> 'Float':
        return -Float(self)

class List(list):
    def __bool__(self) -> bool:
        return True

    def __getitem__(self, idx: Any) -> Any:
        return wrap(list.__getitem__(self, _numerify(idx)))

    def __add__(self, other: Any) -> 'List':
        return _list_op(self, wrap(other), lambda a, b: a + b)
    def __radd__(self, other: Any) -> 'List':
        return _list_op(wrap(other), self, lambda a, b: a + b)

    def __sub__(self, other: Any) -> 'List':
        return _list_op(self, wrap(other), lambda a, b: a - b)
    def __rsub__(self, other: Any) -> 'List':
        return _list_op(wrap(other), self, lambda a, b: a - b)

    def __mul__(self, other: Any) -> 'List':
        return _list_op(self, wrap(other), lambda a, b: a * b)
    def __rmul__(self, other: Any) -> 'List':
        return _list_op(wrap(other), self, lambda a, b: a * b)

    def __truediv__(self, other: Any) -> 'List':
        return _list_op(self, wrap(other), lambda a, b: a / b)
    def __rtruediv__(self, other: Any) -> 'List':
        return _list_op(wrap(other), self, lambda a, b: a / b)

    def __floordiv__(self, other: Any) -> 'List':
        return _list_op(self, wrap(other), lambda a, b: a // b)
    def __rfloordiv__(self, other: Any) -> 'List':
        return _list_op(wrap(other), self, lambda a, b: a // b)

    def __pow__(self, other: Any) -> 'List':
        return _list_op(self, wrap(other), lambda a, b: a ** b)
    def __rpow__(self, other: Any) -> 'List':
        return _list_op(wrap(other), self, lambda a, b: a ** b)

    def __neg__(self) -> 'List':
        return List(-x for x in self)

_listify = lambda v: List(wrap(x) for x in v)
_wrappers = { int: Float, float: Float, str: Str, list: _listify, tuple: _listify, set: _listify, dict: lambda v: List(wrap(x) for x in v.items()) }
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

def rand(a: Any, b: Any) -> Union[Float, List]:
    '''
    Returns a random number in the range `[a, b]`.

    If both `a` and `b` are integer-valued (including floats holding integer values), returns an integer.
    Otherwise, returns a float in the continuous range.
    '''
    def single(a, b):
        a, b = float(a), float(b)
        if a == b: return wrap(a)
        if a > b: a, b = b, a

        ai, bi = int(a), int(b)
        if ai == a and bi == b:
            return wrap(random.randint(ai, bi))
        return wrap(a + random.random() * (b - a))
    return _list_op(wrap(a), wrap(b), single)

def lnot(value: Any) -> Any:
    value = wrap(value)
    return List(lnot(x) for x in value) if isinstance(value, List) else not value

if __name__ == '__main__':
    assert is_wrapped(True)
    v = wrap('hello world') ; assert v is wrap(v) and isinstance(v, Str) and isinstance(v, str)
    v = wrap(1223847982) ; assert v is wrap(v) and isinstance(v, Float) and isinstance(v, float)
    v = wrap(1223847982.453) ; assert v is wrap(v) and isinstance(v, Float) and isinstance(v, float)
    v = wrap([1,4,2,5,43]) ; assert v is wrap(v) and isinstance(v, List) and isinstance(v, list)
    v = wrap((1,4,2,5,43)) ; assert v is wrap(v) and isinstance(v, List) and isinstance(v, list)
    v = wrap({1,3,2,54}) ; assert v is wrap(v) and isinstance(v, List) and isinstance(v, list)
    v = wrap({1:1,3:4,2:2,54:3}) ; assert v is wrap(v) and isinstance(v, List) and isinstance(v, list)
    assert all(isinstance(x, List) and len(x) == 2 for x in v)
    assert v[1][0] == 3 and v[1][1] == 4 and v[-1][0] == 54 and v[-1][-1] == 3
    v = wrap([]) ; v.append(5) ; assert is_wrapped(v['0'])
    v = wrap([{'foo': 'bar'}]) ; assert isinstance(list.__getitem__(v, 0), List) and isinstance(list.__getitem__(list.__getitem__(v, 0), 0), List)
    assert list.__getitem__(list.__getitem__(v, 0), 0) == ['foo', 'bar'] and is_wrapped(list.__getitem__(list.__getitem__(list.__getitem__(v, 0), 0), 0))
    assert is_wrapped(list.__getitem__(list.__getitem__(list.__getitem__(v, 0), 0), 1))
    v = wrap(({'foo': 'bar'},)) ; assert isinstance(list.__getitem__(v, 0), List) and isinstance(list.__getitem__(list.__getitem__(v, 0), 0), List)
    assert list.__getitem__(list.__getitem__(v, 0), 0) == ['foo', 'bar'] and is_wrapped(list.__getitem__(list.__getitem__(list.__getitem__(v, 0), 0), 0))
    assert is_wrapped(list.__getitem__(list.__getitem__(list.__getitem__(v, 0), 0), 1))

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

    assert wrap(5) * wrap(5) == 25 and wrap(5) * wrap('5') == 25 and wrap('5') * wrap(5) == 25 and wrap('5') * wrap('5') == 25
    assert 5 * wrap(5) == 25 and wrap(5) * 5 == 25 and wrap('5') * 5 == 25 and wrap('5') * '5' == 25
    assert 5.25 * wrap(4) == 21 and wrap(5.25) * 4 == 21 and wrap('5.25') * 4 == 21 and wrap('5.25') * '4' == 21
    assert isinstance(wrap(5.25) * 4, Float) and isinstance(wrap('5.25') * 4, Float) and isinstance(wrap('5.25') * '4', Float)
    assert wrap(1000) ** wrap(1000) == math.inf

    assert wrap([1,2,3]) + wrap(['6.0',2,-2]) == [7,4,1] and wrap([1,2,3]) - wrap([6,2,-2]) == [-5,0,5] and wrap([1,2,3]) - wrap([6,2]) == [-5,0] and wrap([1]) - wrap([6,2]) == [-5]
    assert wrap([[1,5,2], [1,2], [0], []]) + wrap('4') == [[5,9,6], [5,6], [4], []] and wrap([[1,5,2], [1,2], [0], []]) + '4' == [[5,9,6], [5,6], [4], []]
    assert wrap([[1,5,2], [1,2], [0], []]) - wrap('2') == [[-1,3,0], [-1,0], [-2], []]
    assert wrap([[1,5,2], [1,2], [0], []]) * wrap('2') == [[2,10,4], [2,4], [0], []]
    assert wrap([[1,5,2], [1,2], [0], []]) - '2' == [[-1,3,0], [-1,0], [-2], []]
    assert wrap([1,2,3]) + 3 == [4,5,6] and wrap([1,2,3]) + wrap(3) == [4,5,6] and wrap([1,2,3]) + '3' == [4,5,6] and wrap([1,2,3]) + wrap('3') == [4,5,6]
    assert 5 + wrap([3,2,5]) == [8,7,10] and wrap(5) + wrap([3,2,5]) == [8,7,10] and '5' + wrap([3,2,5]) == [8,7,10] and wrap('5') + wrap([3,2,5]) == [8,7,10]
    assert wrap([4,7,2])[0] == 4 and wrap([4,7,2])[wrap(1.0)] == 7 and len(wrap([4,7,2])) == 3

    assert wrap([[1,[5],2], [1,2], [0], []]) + wrap(['1.0',3,2]) == [[2,[8],4], [2,5], [1], []]
    assert wrap([[1,5,2], [1,2], [0], []]) - wrap(['1.0',3,2]) == [[0,2,0], [0,-1], [-1], []]
    assert wrap([[1,5,2], [1,2], ['0'], 3]) - wrap(['1',3.0,2]) == [[0,2,0], [0,-1], [-1], [2,0,1]]
    assert wrap([[1,5,2], [1,2], [0], []]) * wrap([1,3,2]) == [[1,15,4], [1,6], [0], []]
    assert wrap([[1,5,2], [1,2], [0], '3']) * wrap([1,3,2]) == [[1,15,4], [1,6], [0], [3,9,6]]
    assert wrap([[1,5,2], [1,2], [0], []]) / wrap([1,'3.0',2]) * 3 == [[3,5,3], [3,2], [0], []]
    assert wrap([[1,5,2], [1,'2'], [0], '3']) / wrap([1,3,2]) * 6 == [[6,10,6], [6,4], [0], [18,6,9]]
    assert wrap([[1,5,2], [1,2], [0], []]) // wrap([1,3,2]) == [[1,1,1], [1,0], [0], []]
    assert wrap([[1,'5',2], [1,2], [0], 3]) // wrap(['1.0',3,2.0]) == [[1,1,1], [1,0], [0], [3,1,1]]
    assert wrap([[1,5.0,2], [1,2], [0], []]) ** wrap([1,3,2]) == [[1,125,4], [1,8], [0], []]
    assert wrap([[1,'5',2], [1,2.0], [0], 3]) ** wrap(['1.0',3,2.0]) == [[1,125,4], [1,8], [0], [3,27,9]]

    assert wrap(3) == wrap('3') and wrap(3.0) == wrap('3') and wrap(3) == wrap('3.0') and wrap(3.0) == wrap('3.0')
    assert -wrap(3) == -wrap('3') and is_wrapped(-wrap(3)) and is_wrapped(-wrap('4'))
    assert not [] and wrap([]) and wrap(wrap([]))
    assert len(wrap([6,2,4])) == wrap('3')

    assert is_wrapped(wrap(3) + wrap(3)) and is_wrapped(wrap(3) - wrap(3)) and is_wrapped(3 - wrap(3)) and is_wrapped(wrap(3) - 3)
    assert 3 + wrap(3) == 6 and is_wrapped(3 + wrap(3)) and is_wrapped(wrap(3) - 3) and 3 - wrap(2) == 1 and is_wrapped(3 - wrap(2)) and is_wrapped(wrap(3) - 2)
    assert is_wrapped(wrap(3.75) + wrap(2.5)) and is_wrapped(wrap(3.75) - wrap(2.5)) and is_wrapped(wrap(3.75) - 2.5) and is_wrapped(3.75 - wrap(2.5))
    assert wrap(3.75) + wrap(2.5) == 6.25 and wrap(3.75) - wrap(2.5) == 1.25 and 3.75 - wrap(2.5) == 1.25 and wrap(3.75) - 2.5 == 1.25
    assert is_wrapped(wrap('3') + wrap('3')) and is_wrapped(wrap('3') - wrap('3')) and is_wrapped('3' - wrap('3')) and is_wrapped(wrap('3') - '3')
    assert wrap('3') + wrap('7') == 10 and wrap('3') + '7' == 10 and isinstance(wrap('3') + wrap('7'), Float) and isinstance(wrap('3') + '7', Float)
    assert is_wrapped(wrap('3') + wrap(3)) and is_wrapped(wrap('3') - wrap(3)) and is_wrapped('3' - wrap(3)) and is_wrapped(wrap('3') - 3)
    assert is_wrapped(wrap('3') + wrap(3.9)) and is_wrapped(wrap('3') - wrap(3.8)) and is_wrapped('3' - wrap(3.7)) and is_wrapped(wrap('3') - 3.6)
    assert wrap('3') + wrap(7) == 10 and wrap('3') + 7 == 10 and isinstance(wrap('3') + wrap(7), Float) and isinstance(wrap('3') + 7, Float) and isinstance(wrap('3.0') + 7, Float)
    assert wrap('3') + wrap(7.5) == 10.5 and wrap('3') + 7.5 == 10.5 and isinstance(wrap('3.5') + wrap(7.5), Float) and isinstance(wrap('3.5') + 7.5, Float)

    print('passed all snap wrapper tests')
