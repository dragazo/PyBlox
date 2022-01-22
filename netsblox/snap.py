import random
import math

from typing import Any, Union, Callable

def _numerify(val: Any) -> Union[int, float]:
    vf = float(val)
    vi = int(vf)
    return vi if vi == vf else vf
def _list_depth(val: Any) -> int:
    val = wrap(val)
    if isinstance(val, List):
        return 1 if len(val) == 0 else 1 + max(_list_depth(x) for x in val)
    return 0

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
        other = wrap(other)
        if isinstance(other, List): return other.__rsub__(self)
        return wrap(int(self) - _numerify(other))
    def __rsub__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) - self
        return wrap(_numerify(other) - int(self))

    def __mul__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__rmul__(self)
        return wrap(int(self) * _numerify(other))
    def __rmul__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) * self
        return wrap(_numerify(other) * int(self))

    def __truediv__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__rtruediv__(self)
        return wrap(int(self) / _numerify(other))
    def __rtruediv__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) / self
        return wrap(_numerify(other) / int(self))

    def __floordiv__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__rfloordiv__(self)
        return wrap(int(self) // _numerify(other))
    def __rfloordiv__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) // self
        return wrap(_numerify(other) // int(self))

    def __pow__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__rpow__(self)
        return wrap(int(self) ** _numerify(other))
    def __rpow__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) ** self
        return wrap(_numerify(other) ** int(self))

    def __neg__(self) -> 'Int':
        return Int(-int(self))

class Float(float):
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str): return wrap(float(self) == float(other))
        return wrap(float(self) == other)

    def __bool__(self) -> bool:
        return self != 0 and not math.isnan(self)

    def __add__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__radd__(self)
        return wrap(_numerify(float(self) + float(other)))
    def __radd__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) + self
        return wrap(_numerify(float(other) + float(self)))

    def __sub__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__rsub__(self)
        return wrap(_numerify(float(self) - float(other)))
    def __rsub__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) - self
        return wrap(_numerify(float(other) - float(self)))

    def __mul__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__rmul__(self)
        return wrap(_numerify(float(self) * float(other)))
    def __rmul__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) * self
        return wrap(_numerify(float(other) * float(self)))

    def __truediv__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__rtruediv__(self)
        return wrap(_numerify(float(self) / float(other)))
    def __rtruediv__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) / self
        return wrap(_numerify(float(other) / float(self)))

    def __floordiv__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__rfloordiv__(self)
        return wrap(_numerify(float(self) // float(other)))
    def __rfloordiv__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) // self
        return wrap(_numerify(float(other) // float(self)))

    def __pow__(self, other: Any) -> Any:
        other = wrap(other)
        if isinstance(other, List): return other.__rpow__(self)
        return wrap(_numerify(float(self) ** float(other)))
    def __rpow__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) ** self
        return wrap(_numerify(float(other) ** float(self)))

    def __neg__(self) -> Union['Int', 'Float']:
        return wrap(-_numerify(self))

class Str(str):
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, int) or isinstance(other, float): return float(self) == other
        return str(self) == other

    def __cvt(self) -> Union[Int, Float]:
        return wrap(_numerify(self))

    def __add__(self, other: Any) -> Any:
        return self.__cvt() + other
    def __radd__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) + self
        return wrap(other + _numerify(self))

    def __sub__(self, other: Any) -> Any:
        return self.__cvt() - other
    def __rsub__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) - self
        return wrap(other - _numerify(self))

    def __mul__(self, other: Any) -> Any:
        return self.__cvt() * wrap(other)
    def __rmul__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) * self
        return wrap(other * _numerify(self))

    def __truediv__(self, other: Any) -> Any:
        return self.__cvt() / wrap(other)
    def __rtruediv__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) / self
        return wrap(other / _numerify(self))

    def __floordiv__(self, other: Any) -> Any:
        return self.__cvt() // wrap(other)
    def __rfloordiv__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) // self
        return wrap(other // _numerify(self))

    def __pow__(self, other: Any) -> Any:
        return self.__cvt() ** wrap(other)
    def __rpow__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) ** self
        return wrap(other ** _numerify(self))

    def __neg__(self) -> Union['Int', 'Float']:
        return -self.__cvt()

class List(list):
    def __bool__(self) -> bool:
        return True

    def __getitem__(self, idx: Any) -> Any:
        return wrap(list.__getitem__(self, _numerify(idx)))

    def __list_op(self, other: Any, op: Callable) -> 'List':
        other = wrap(other)
        if isinstance(other, List):
            if _list_depth(self) == _list_depth(other):
                return List(op(wrap(self[i]), wrap(other[i])) for i in range(min(len(self), len(other))))
            return List(op(wrap(x), other) for x in self)
        return List(op(wrap(x), other) for x in self)
    def __list_rop(self, other: Any, op: Callable) -> 'List':
        other = wrap(other)
        return List(op(other, x) for x in self)

    def __add__(self, other: Any) -> 'List':
        return self.__list_op(other, lambda a, b: a + b)
    def __radd__(self, other: Any) -> 'List':
        return self.__list_rop(other, lambda a, b: a + b)

    def __sub__(self, other: Any) -> 'List':
        return self.__list_op(other, lambda a, b: a - b)
    def __rsub__(self, other: Any) -> 'List':
        return self.__list_rop(other, lambda a, b: a - b)

    def __mul__(self, other: Any) -> 'List':
        return self.__list_op(other, lambda a, b: a * b)
    def __rmul__(self, other: Any) -> 'List':
        return self.__list_rop(other, lambda a, b: a * b)

    def __truediv__(self, other: Any) -> 'List':
        return self.__list_op(other, lambda a, b: a / b)
    def __rtruediv__(self, other: Any) -> 'List':
        return self.__list_rop(other, lambda a, b: a / b)

    def __floordiv__(self, other: Any) -> 'List':
        return self.__list_op(other, lambda a, b: a // b)
    def __rfloordiv__(self, other: Any) -> 'List':
        return self.__list_rop(other, lambda a, b: a // b)

    def __pow__(self, other: Any) -> 'List':
        return self.__list_op(other, lambda a, b: a ** b)
    def __rpow__(self, other: Any) -> 'List':
        return self.__list_rop(other, lambda a, b: a ** b)

    def __neg__(self) -> 'List':
        return List(-x for x in self)

_listify = lambda v: List(wrap(x) for x in v)
_wrappers = { int: Int, float: Float, str: Str, list: _listify, tuple: _listify, set: _listify, dict: lambda v: List(wrap(x) for x in v.items()) }
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
    assert is_wrapped(True)
    v = wrap('hello world') ; assert v is wrap(v) and isinstance(v, Str) and isinstance(v, str)
    v = wrap(1223847982) ; assert v is wrap(v) and isinstance(v, Int) and isinstance(v, int)
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
    assert isinstance(wrap(5.25) * 4, Int)
    assert isinstance(wrap('5.25') * 4, Int)
    assert isinstance(wrap('5.25') * '4', Int)

    assert wrap([1,2,3]) + wrap(['6.0',2,-2]) == [7,4,1] and wrap([1,2,3]) - wrap([6,2,-2]) == [-5,0,5] and wrap([1,2,3]) - wrap([6,2]) == [-5,0] and wrap([1]) - wrap([6,2]) == [-5]
    assert wrap([[1,5,2], [1,2], [0], []]) + wrap('4') == [[5,9,6], [5,6], [4], []] and wrap([[1,5,2], [1,2], [0], []]) + '4' == [[5,9,6], [5,6], [4], []]
    assert wrap([[1,5,2], [1,2], [0], []]) - wrap('2') == [[-1,3,0], [-1,0], [-2], []]
    assert wrap([[1,5,2], [1,2], [0], []]) * wrap('2') == [[2,10,4], [2,4], [0], []]
    assert wrap([[1,5,2], [1,2], [0], []]) - '2' == [[-1,3,0], [-1,0], [-2], []]
    assert wrap([1,2,3]) + 3 == [4,5,6] and wrap([1,2,3]) + wrap(3) == [4,5,6] and wrap([1,2,3]) + '3' == [4,5,6] and wrap([1,2,3]) + wrap('3') == [4,5,6]
    assert 5 + wrap([3,2,5]) == [8,7,10] and wrap(5) + wrap([3,2,5]) == [8,7,10] and '5' + wrap([3,2,5]) == [8,7,10] and wrap('5') + wrap([3,2,5]) == [8,7,10]
    assert wrap([4,7,2])[0] == 4 and wrap([4,7,2])[wrap(1.0)] == 7 and len(wrap([4,7,2])) == 3

    assert _list_depth(2.3) == 0 and _list_depth([]) == 1 and _list_depth([[]]) == 2 and _list_depth([[True]]) == 2
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
    assert wrap('3') + wrap('7') == 10 and wrap('3') + '7' == 10 and isinstance(wrap('3') + wrap('7'), Int) and isinstance(wrap('3') + '7', Int)
    assert is_wrapped(wrap('3') + wrap(3)) and is_wrapped(wrap('3') - wrap(3)) and is_wrapped('3' - wrap(3)) and is_wrapped(wrap('3') - 3)
    assert is_wrapped(wrap('3') + wrap(3.9)) and is_wrapped(wrap('3') - wrap(3.8)) and is_wrapped('3' - wrap(3.7)) and is_wrapped(wrap('3') - 3.6)
    assert wrap('3') + wrap(7) == 10 and wrap('3') + 7 == 10 and isinstance(wrap('3') + wrap(7), Int) and isinstance(wrap('3') + 7, Int) and isinstance(wrap('3.0') + 7, Int)
    assert wrap('3') + wrap(7.5) == 10.5 and wrap('3') + 7.5 == 10.5 and isinstance(wrap('3.5') + wrap(7.5), Int) and isinstance(wrap('3.5') + 7.5, Int)

    print('passed all snap wrapper tests')
