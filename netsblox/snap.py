import random
import math

from typing import Any, Union, Callable, Sequence

def _is_matrix(v: Any) -> bool:
    return isinstance(v, list) and len(v) > 0 and isinstance(list.__getitem__(v, 0), list)
def _is_list(v: Any) -> bool:
    return isinstance(v, list)

def _list_binary_op(a: Any, b: Any, op: Callable, matrix_mode: bool = True) -> 'List':
    assert is_wrapped(a) and is_wrapped(b)
    checker = _is_matrix if matrix_mode else _is_list
    if checker(a):
        if checker(b):
            return List(_list_binary_op(wrap(list.__getitem__(a, i)), wrap(list.__getitem__(b, i)), op, matrix_mode) for i in range(min(len(a), len(b))))
        return List(_list_binary_op(wrap(list.__getitem__(a, i)), b, op, matrix_mode) for i in range(len(a)))
    if checker(b):
        return List(_list_binary_op(a, wrap(list.__getitem__(b, i)), op, matrix_mode) for i in range(len(b)))
    return _list_binary_op(a, b, op, False) if matrix_mode else op(a, b)
def _list_unary_op(a: Any, op: Callable) -> 'List':
    assert is_wrapped(a)
    if _is_list(a):
        return List(_list_unary_op(wrap(x), op) for x in a)
    return op(a)

def _scalar_op(a: Any, b: Any, op: Callable) -> 'Float':
    a, b = float(a), float(b)
    try:
        return Float(op(a, b))
    except OverflowError:
        return Float(math.inf)

def _parse_index(idx: Any) -> Union['List', int, str]:
    idx = wrap(idx)
    if type(idx) is List: return idx

    try:
        idx = +idx
    except:
        return str(idx)

    return idx if type(idx) is int else str(idx)

def _float_div(a: Any, b: Any) -> 'Float':
    a, b = float(a), float(b)
    if b != 0: return Float(a / b)
    if a == 0: return Float(math.nan)
    return Float(math.inf if a > 0 else -math.inf)

class Float(float):
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str): return wrap(float(self) == float(other))
        return wrap(float(self) == other)

    def __str__(self) -> str:
        if math.isnan(self): return 'NaN'
        if math.isinf(self): return 'Infinity' if self > 0 else '-Infinity'
        return str(+self)

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
        return _scalar_op(self, other, _float_div)
    def __rtruediv__(self, other: Any) -> Any:
        if not is_wrapped(other): return wrap(other) / self
        return _scalar_op(other, self, _float_div)

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
    def __pos__(self) -> Union[int, float]:
        vf = float(self)
        if not math.isfinite(vf): return vf
        vi = int(vf)
        return vi if vi == vf else vf
    def __abs__(self) -> 'Float':
        return Float(abs(float(self)))
    def __round__(self) -> 'Float':
        return Float(round(float(self)))
    def __trunc__(self) -> 'Float':
        return Float(math.trunc(float(self)))
    def __ceil__(self) -> 'Float':
        return Float(math.ceil(float(self)))
    def __floor__(self) -> 'Float':
        return Float(math.floor(float(self)))

class Str(str):
    def __getitem__(self, idx: Any) -> str:
        idx = _parse_index(idx)
        t = type(idx)
        if t is List: return _list_unary_op(idx, lambda x: self[+x])
        elif t is str: return wrap('')
        elif t is int:
            if idx < 0 or idx >= len(self): return wrap('')
            else: return str.__getitem__(self, idx)
        else: assert False

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
    def __pos__(self) -> Union[int, float]:
        return +Float(self)
    def __abs__(self) -> 'Float':
        return Float(abs(Float(self)))
    def __round__(self) -> 'Float':
        return round(Float(self))
    def __trunc__(self) -> 'Float':
        return math.trunc(Float(self))
    def __ceil__(self) -> 'Float':
        return math.ceil(Float(self))
    def __floor__(self) -> 'Float':
        return math.floor(Float(self))

class List(list):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # these are volatile - we don't persist them on e.g. list concat and they don't count toward size, indexing, etc.
        self.__str_keys = {}

    def __bool__(self) -> bool:
        return True

    def __delitem__(self, idx: Any) -> None:
        idx = _parse_index(idx)
        t = type(idx)
        if t is List: pass
        elif t is str: del self.__str_keys[idx]
        elif t is int:
            if idx < 0: del self.__str_keys[str(idx)]
            elif idx < len(self): list.__delitem__(self, idx)
            else: pass
        else: assert False
    def __getitem__(self, idx: Any) -> Any:
        idx = _parse_index(idx)
        t = type(idx)
        if t is List: return wrap('')
        elif t is str: return wrap(self.__str_keys.get(idx, ''))
        elif t is int:
            if idx < 0: return wrap(self.__str_keys.get(str(idx), ''))
            elif idx < len(self): return wrap(list.__getitem__(self, idx))
            else: return wrap('')
        else: assert False
    def __setitem__(self, idx: Any, value: Any):
        value = wrap(value)
        idx = _parse_index(idx)
        t = type(idx)
        if t is List: pass
        elif t is str: self.__str_keys[idx] = value
        elif t is int:
            if idx < 0: self.__str_keys[str(idx)] = value
            elif idx < len(self): list.__setitem__(self, idx, value)
            else:
                for _ in range(len(self), idx):
                    self.append(wrap(''))
                self.append(value)
        else: assert False

    def __iter__(self) -> Sequence[Any]:
        return (wrap(x) for x in list.__iter__(self))

    def __add__(self, other: Any) -> 'List':
        return _list_binary_op(self, wrap(other), lambda a, b: a + b)
    def __radd__(self, other: Any) -> 'List':
        return _list_binary_op(wrap(other), self, lambda a, b: a + b)

    def __sub__(self, other: Any) -> 'List':
        return _list_binary_op(self, wrap(other), lambda a, b: a - b)
    def __rsub__(self, other: Any) -> 'List':
        return _list_binary_op(wrap(other), self, lambda a, b: a - b)

    def __mul__(self, other: Any) -> 'List':
        return _list_binary_op(self, wrap(other), lambda a, b: a * b)
    def __rmul__(self, other: Any) -> 'List':
        return _list_binary_op(wrap(other), self, lambda a, b: a * b)

    def __truediv__(self, other: Any) -> 'List':
        return _list_binary_op(self, wrap(other), lambda a, b: a / b)
    def __rtruediv__(self, other: Any) -> 'List':
        return _list_binary_op(wrap(other), self, lambda a, b: a / b)

    def __floordiv__(self, other: Any) -> 'List':
        return _list_binary_op(self, wrap(other), lambda a, b: a // b)
    def __rfloordiv__(self, other: Any) -> 'List':
        return _list_binary_op(wrap(other), self, lambda a, b: a // b)

    def __pow__(self, other: Any) -> 'List':
        return _list_binary_op(self, wrap(other), lambda a, b: a ** b)
    def __rpow__(self, other: Any) -> 'List':
        return _list_binary_op(wrap(other), self, lambda a, b: a ** b)

    def __neg__(self) -> 'List':
        return List(-x for x in self)
    def __abs__(self) -> 'List':
        return List(abs(x) for x in self)
    def __round__(self) -> 'List':
        return List(round(x) for x in self)
    def __trunc__(self) -> 'List':
        return List(math.trunc(x) for x in self)
    def __ceil__(self) -> 'List':
        return List(math.ceil(x) for x in self)
    def __floor__(self) -> 'List':
        return List(math.floor(x) for x in self)

    def random(self) -> Any:
        if len(self) == 0: return wrap('')
        return wrap(random.choice(self))
    def last(self) -> Any:
        if len(self) == 0: return wrap('')
        return wrap(list.__getitem__(self, -1))
    def pop(self) -> Any:
        if len(self) == 0: return wrap('')
        res = wrap(list.__getitem__(self, -1))
        list.__delitem__(self, -1)
        return res
    def all_but_first(self) -> 'List':
        if len(self) == 0: return List()
        return wrap(list.__getitem__(self, slice(1, len(self))))

    def index(self, *args, **kwargs) -> Float:
        try:
            return Float(list.index(self, *args, **kwargs))
        except ValueError:
            return Float(-1)

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
        a, b = +wrap(a), +wrap(b)
        if a == b: return wrap(a)
        if a > b: a, b = b, a

        ai, bi = int(a), int(b)
        if ai == a and bi == b:
            return wrap(random.randint(ai, bi))
        return wrap(a + random.random() * (b - a))
    return _list_binary_op(wrap(a), wrap(b), single)

def sxrange(a: Any, b: Any) -> Sequence[Any]:
    '''
    Returns a sequence of numbers starting at `a` and going up to and including `b`,
    increasing or decreasing by `1` each step depending on if `a < b` or `b < a`.
    The initial point, `a` is always included in the resulting sequence.

    This is similar to `srange` except that it does not have to actually create a list of all the items.
    For instance, you `srange(1, 1000000)` would create a (large) list of one million items,
    whereas `sxrange(1, 1000000)` simply generates the numbers one at a times as needed.
    '''
    def single(a, b):
        a, b = +wrap(a), +wrap(b)
        step = 1 if b > a else -1
        return (a + wrap(i * step) for i in range(math.floor(abs(b - a)) + 1))
    return _list_binary_op(wrap(a), wrap(b), single)
def srange(a: Any, b: Any) -> List:
    '''
    Returns the list of numbers starting at `a` and going up to and including `b`,
    increasing or decreasing by `1` each step depending on if `a < b` or `b < a`.
    The initial point, `a`, is always included in the resulting list.

    Equivalent to collecting all of the sequences returned by `sxrange` into lists.
    '''
    return _list_unary_op(sxrange(a, b), List)

def sqrt(value: Any) -> Any:
    return _list_unary_op(wrap(value), lambda x: wrap(math.sqrt(+x)))
def lnot(value: Any) -> Any:
    return _list_unary_op(wrap(value), lambda x: not x)

def sin(value: Any) -> Any:
    return _list_unary_op(wrap(value), lambda x: wrap(math.sin(+x * (math.pi / 180))))
def cos(value: Any) -> Any:
    return _list_unary_op(wrap(value), lambda x: wrap(math.cos(+x * (math.pi / 180))))
def tan(value: Any) -> Any:
    return _list_unary_op(wrap(value), lambda x: wrap(math.tan(+x * (math.pi / 180))))

def asin(value: Any) -> Any:
    return _list_unary_op(wrap(value), lambda x: wrap(math.asin(+x) * (180 / math.pi)))
def acos(value: Any) -> Any:
    return _list_unary_op(wrap(value), lambda x: wrap(math.acos(+x) * (180 / math.pi)))
def atan(value: Any) -> Any:
    return _list_unary_op(wrap(value), lambda x: wrap(math.atan(+x) * (180 / math.pi)))

def get_ord(value: Any) -> Any:
    return _list_unary_op(wrap(value), lambda x: wrap(ord(str(x))))
def get_chr(value: Any) -> Any:
    return _list_unary_op(wrap(value), lambda x: wrap(chr(+x)))

def identical(a: Any, b: Any) -> Any:
    a, b = wrap(a), wrap(b)
    la, lb = _is_list(a), _is_list(b)
    if la and lb: return a is b
    if la or lb: return False
    return a == b

if __name__ == '__main__':
    assert is_wrapped(True)
    v = wrap('hello world') ; assert v is wrap(v) and isinstance(v, Str) and isinstance(v, str)
    v = wrap(1223847982) ; assert v is wrap(v) and isinstance(v, Float) and isinstance(v, float)
    v = wrap(1223847982.453) ; assert v is wrap(v) and isinstance(v, Float) and isinstance(v, float)
    v = wrap([1,4,2,5,43]) ; assert v is wrap(v) and isinstance(v, List) and isinstance(v, list)
    assert all(is_wrapped(v[i]) for i in range(len(v))) ; v.append('hello world') ; assert all(is_wrapped(v[i]) for i in range(len(v)))
    assert all(is_wrapped(x) for x in v) ; v.append(12) ; assert all(is_wrapped(x) for x in v)
    v = wrap((1,4,2,5,43)) ; assert v is wrap(v) and isinstance(v, List) and isinstance(v, list)
    v = wrap({1,3,2,54}) ; assert v is wrap(v) and isinstance(v, List) and isinstance(v, list)
    v = wrap({1:1,3:4,2:2,54:3}) ; assert v is wrap(v) and isinstance(v, List) and isinstance(v, list)
    assert all(isinstance(x, List) and len(x) == 2 for x in v)
    assert v[1][0] == 3 and v[1][1] == 4 and v.last()[0] == 54 and v.last().last() == 3
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

    assert type(+wrap(34)) is int and type(+wrap(34.53)) is float and type(+wrap('34')) is int and type(+wrap('34.53')) is float

    assert srange(wrap(6), wrap(6)) == [6] and srange(wrap(4), wrap(7)) == [4, 5, 6, 7] and srange(wrap(4), wrap('6.9')) == [4, 5, 6]
    assert srange(wrap('5.25'), wrap('10.4')) == [5.25, 6.25, 7.25, 8.25, 9.25, 10.25] and srange(wrap('10.5'), wrap(5.25)) == [10.5, 9.5, 8.5, 7.5, 6.5, 5.5]
    assert srange(wrap('5.5'), wrap(5.25)) == [5.5] and srange(wrap('5.5'), wrap(5.5)) == [5.5] and srange(wrap('5.5'), wrap(5.75)) == [5.5]
    assert srange(wrap([2,3]), wrap([10, 6])) == [[2,3,4,5,6,7,8,9,10],[3,4,5,6]]
    assert srange(wrap([2,'3.125']), wrap([10, ['-6.7'], 3])) == [[2,3,4,5,6,7,8,9,10],[[3.125, 2.125, 1.125, 0.125, -0.875, -1.875, -2.875, -3.875, -4.875, -5.875]]]
    assert is_wrapped(sqrt(wrap(25))) and is_wrapped(sqrt(wrap('25.0'))) and is_wrapped(sqrt(wrap([25, ['49', 16], '4.0'])))
    assert sqrt(wrap(25)) == 5 and sqrt(wrap('25.0')) == 5 and sqrt(wrap([25, ['49', 16], '4.0'])) == [5, [7, 4], 2]

    assert is_wrapped(round(wrap(25.2))) and is_wrapped(round(wrap('25.56'))) and is_wrapped(round(wrap([[12.2, 24, [['-346.3'], 0], '12.9']])))
    assert round(wrap(25.2)) == 25 and round(wrap('25.56')) == 26 and round(wrap([[12.2, 24, [['-346.3'], 0], '12.9']])) == [[12, 24, [[-346], 0], 13]]

    vv = sxrange(wrap(1.25), wrap(1e300)) ; assert not isinstance(vv, list) and not isinstance(vv, tuple)
    assert sxrange(1, 100) != srange(1, 100) # generator != list
    assert list(sxrange(wrap(12.2), wrap('-6.7'))) == srange(wrap(12.2), wrap('-6.7'))

    v = wrap([1,4,2,3,2])
    assert v[wrap('1')] == 4 and is_wrapped(v[wrap('1')]) and v['4'] == 2 and is_wrapped(v['4'])
    assert v[34] == '' and is_wrapped(v[34])
    assert v.index(wrap('4')) == 1 and v.index('4') == 1 and v.index(4.0) == 1 and v.index('2') == 2 and is_wrapped(v.index('2'))
    assert v.index(7) == -1 and is_wrapped(v.index(7))
    assert wrap([]).random() == '' and is_wrapped(wrap([]).random())
    assert wrap([]).last() == '' and is_wrapped(wrap([]).last())
    assert wrap([3]).last() == 3 and is_wrapped(wrap([3]).last())
    assert wrap([3, 46]).last() == 46 and is_wrapped(wrap([3, 46]).last())
    assert wrap([3, 101, 46]).last() == 46 and is_wrapped(wrap([3, 101, 46]).last())

    assert identical(wrap('768') + wrap('0'), wrap('768')) and identical(wrap('768') + wrap('0'), wrap(768))
    assert not identical(wrap([1,2,3]), wrap([1,2,3]))
    v = wrap([1,2,3]) ; assert identical(v, v)

    assert abs(wrap('-45')) == 45 and is_wrapped(abs(wrap('-45')))
    assert abs(wrap(-45)) == 45 and is_wrapped(abs(wrap(-45)))
    assert abs(wrap(['-45', 4, -4])) == [45,4,4] and is_wrapped(abs(wrap(['-45', 4, -4])))

    v = round(wrap([1, 3.4, 6.7, -4.2, '-8.8'])) ; assert v == [1, 3, 7, -4, -9] and is_wrapped(v)
    v = math.trunc(wrap([1, 3.4, '6.7', -4.2, -8.8])) ; assert v == [1, 3, 6, -4, -8] and is_wrapped(v)
    v = math.ceil(wrap([1, '3.4', 6.7, -4.2, -8.8])) ; assert v == [1, 4, 7, -4, -8] and is_wrapped(v)
    v = math.floor(wrap([1, '3.4', 6.7, -4.2, -8.8])) ; assert v == [1, 3, 6, -5, -9] and is_wrapped(v)

    v = wrap([])
    v[wrap('14.5')] = 'test 1'
    v[wrap('-14.5')] = 'test 2'
    v[wrap(7.5)] = 'test 3'
    v[wrap(-7.5)] = 'test 4'
    v[wrap('hello pony')] = 'test 5'
    assert len(v) == 0 and v == []
    assert v[wrap('14.5')] == 'test 1' and is_wrapped(v[wrap('14.5')]) and v[wrap('-14.5')] == 'test 2' and is_wrapped(v[wrap('-14.5')])
    assert v[wrap(7.5)] == 'test 3' and is_wrapped(v[wrap(7.5)]) and v[wrap(-7.5)] == 'test 4' and is_wrapped(v[wrap(-7.5)])
    assert v[wrap('hello pony')] == 'test 5' and is_wrapped(v[wrap('hello pony')])
    assert v[wrap('14.6')] == '' and is_wrapped(v[wrap('14.6')]) and v[wrap('-14.6')] == '' and is_wrapped(v[wrap('-14.6')])
    assert v[wrap(7.6)] == '' and is_wrapped(v[wrap(7.6)]) and v[wrap(-7.6)] == '' and is_wrapped(v[wrap(-7.6)])
    assert v[wrap('hello ponyy')] == '' and is_wrapped(v[wrap('hello ponyy')])
    v[wrap(-5)] = 'test 6'
    v[wrap('-1')] = 'test 7'
    assert len(v) == 0 and v == []
    assert v[wrap(-5)] == 'test 6' and is_wrapped(v[wrap(-5)]) and v[wrap('-5')] == 'test 6' and is_wrapped(v[wrap('-5')])
    assert v[wrap('-1')] == 'test 7' and is_wrapped(v[wrap('-1')]) and v[wrap(-1.0)] == 'test 7' and is_wrapped(v[wrap(-1.0)])
    v[5] = 'test 8'
    assert len(v) == 6 and v == ['', '', '', '', '', 'test 8'] and v[5] == 'test 8' and is_wrapped(v[5])
    v[2] = 'test 9'
    assert len(v) == 6 and v == ['', '', 'test 9', '', '', 'test 8']
    assert len(v) == 6 and v[wrap(-1)] == 'test 7' and v[wrap(-5)] == 'test 6' and v['hello pony'] == 'test 5' and v == ['', '', 'test 9', '', '', 'test 8']
    del v[-1]
    assert len(v) == 6 and v[wrap(-1)] == '' and v[wrap(-5)] == 'test 6' and v['hello pony'] == 'test 5' and v == ['', '', 'test 9', '', '', 'test 8']
    del v['hello pony']
    assert len(v) == 6 and v[wrap(-1)] == '' and v[wrap(-5)] == 'test 6' and v['hello pony'] == '' and v == ['', '', 'test 9', '', '', 'test 8'] and v[5] == 'test 8'
    del v[3]
    assert len(v) == 5 and v[wrap(-1)] == '' and v[wrap(-5)] == 'test 6' and v['hello pony'] == '' and v == ['', '', 'test 9', '', 'test 8'] and v[4] == 'test 8' and v[5] == ''

    assert abs(sin(1) - 0.01745240643728351) < 1e-10 and abs(cos(1) - 0.9998476951563913) < 1e-10 and abs(tan(1) - 0.017455064928217585) < 1e-10
    assert abs(asin(0.75) - 48.590377890729144) < 1e-10 and abs(acos(0.75) - 41.40962210927086) < 1e-10 and abs(atan(0.75) - 36.86989764584402) < 1e-10

    v = get_ord(wrap(["a", "b", ["c", [["d"]], "e"]])) ; assert v == [97, 98, [99, [[100]], 101]] and is_wrapped(v)
    v = get_chr(v) ; assert v == ["a", "b", ["c", [["d"]], "e"]] and is_wrapped(v)

    v = wrap('abcdefghijklmnopqrstuvwxyz')
    assert v[-1] == '' and is_wrapped(v[-1]) and v[123] == '' and is_wrapped(v[123])
    assert v['hello'] == '' and is_wrapped(v['hello'])
    vv = v[[[4,2],2,[[3,1]]]] ; assert vv == [['e', 'c'], 'c', [['d', 'b']]] and is_wrapped(vv)

    v = wrap([])
    vv = v.random() ; assert vv == '' and is_wrapped(vv)
    vv = v.all_but_first() ; assert vv == [] and is_wrapped(vv) and vv is not v and not identical(vv, v)
    v = wrap([7])
    vv = v.random() ; assert vv == 7 and is_wrapped(vv)
    vv = v.all_but_first() ; assert vv == [] and is_wrapped(vv) and vv is not wrap([]).all_but_first()
    v = wrap([3, 6, 3, 8, 7])
    vv = v.all_but_first() ; assert vv == [6, 3, 8, 7] and is_wrapped(vv) and v == [3,6,3,8,7]
    xx = vv.pop() ; assert xx == 7 and is_wrapped(xx) and vv == [6,3,8] and vv.last() == 8 and vv.last() == 8 and is_wrapped(vv.last())
    xx = vv.pop() ; assert xx == 8 and is_wrapped(xx) and vv == [6,3] and vv.last() == 3 and vv.last() == 3 and is_wrapped(vv.last())
    xx = vv.pop() ; assert xx == 3 and is_wrapped(xx) and vv == [6] and vv.last() == 6 and vv.last() == 6 and is_wrapped(vv.last())
    xx = vv.pop() ; assert xx == 6 and is_wrapped(xx) and vv == [] and vv.last() == '' and vv.last() == '' and is_wrapped(vv.last())
    xx = vv.pop() ; assert xx == '' and is_wrapped(xx) and vv == [] and vv.last() == '' and vv.last() == '' and is_wrapped(vv.last())
    xx = vv.pop() ; assert xx == '' and is_wrapped(xx) and vv == [] and vv.last() == '' and vv.last() == '' and is_wrapped(vv.last())
    v = wrap([3, 6, 3, 8, 7])
    assert v == [3,6,3,8,7] and len(v) == 5
    v.clear()
    assert v == [] and len(v) == 0

    assert str(wrap(34)) == '34' and str(wrap(-34.5)) == '-34.5'

    assert bool(wrap(True)) == True and bool(wrap(False)) == False
    assert bool(wrap(5)) and bool(wrap(-2.3)) and not wrap(0) and not wrap(0.0) and not wrap(math.nan)

    assert lnot(wrap(True)) == False and lnot(wrap(False)) == True
    assert lnot('') == True and lnot('h') == False and lnot(0) and lnot(math.nan)
    v = lnot(wrap(['hello', '', True, [0, 4, False, -1], '0'])) ; assert v == [False, True, False, [True, False, True, False], False] and is_wrapped(v)

    assert str(wrap(1) / wrap(0)) == 'Infinity' and str(wrap('1') / wrap('0')) == 'Infinity'
    assert str(wrap(-1) / wrap(0)) == '-Infinity' and str(wrap('-1') / wrap('0')) == '-Infinity'
    assert str(wrap(0) / wrap(0)) == 'NaN' and str(wrap('0') / wrap('0')) == 'NaN'
    assert str(wrap(-0) / wrap(0)) == 'NaN' and str(wrap('-0') / wrap('0')) == 'NaN'

    v = +wrap('Infinity') ; assert v > 0 and math.isinf(v)
    v = +wrap('-Infinity') ; assert v < 0 and math.isinf(v)
    v = +wrap('NaN') ; assert math.isnan(v)

    print('passed all snap wrapper tests')
