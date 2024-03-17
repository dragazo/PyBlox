import random
import math
import re
import io
import json
import csv
import itertools

from typing import Any, Union, Callable, Sequence

import netsblox as _netsblox

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
def _list_fold_op(a: Any, acc: Any, op: Callable) -> 'List':
    assert is_wrapped(acc) and is_wrapped(a) and _is_list(a)
    for i in range(len(a)):
        acc = op(acc, wrap(list.__getitem__(a, i)))
    return acc

def _scalar_op(a: Any, b: Any, op: Callable) -> 'Float':
    a, b = float(a), float(b)
    try:
        return Float(op(a, b))
    except OverflowError:
        return Float(math.inf)

def _single_cmp(a: Any, b: Any) -> int:
    base = lambda x, y: 1 if x > y else -1 if x < y else 0
    try:
        return base(float(a), float(b))
    except:
        return base(str(a), str(b))

def _parse_index(idx: Any) -> Union['List', int, str, slice]:
    idx = wrap(idx)
    if type(idx) is List or type(idx) is slice: return idx

    try:
        idx = +idx
    except:
        pass

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
    def __ne__(self, other: Any) -> bool:
        return not (self == other)

    def __gt__(self, other: Any) -> Any:
        return _list_binary_op(self, wrap(other), lambda a, b: _single_cmp(a, b) > 0)
    def __ge__(self, other: Any) -> Any:
        return _list_binary_op(self, wrap(other), lambda a, b: _single_cmp(a, b) >= 0)
    def __lt__(self, other: Any) -> Any:
        return _list_binary_op(self, wrap(other), lambda a, b: _single_cmp(a, b) < 0)
    def __le__(self, other: Any) -> Any:
        return _list_binary_op(self, wrap(other), lambda a, b: _single_cmp(a, b) <= 0)

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
        if t is slice: return wrap(str.__getitem__(self, idx))
        elif t is List: return _list_unary_op(idx, lambda x: self[+x])
        elif t is str: return wrap('')
        elif t is int:
            if idx < 0 or idx >= len(self): return wrap('')
            else: return wrap(str.__getitem__(self, idx))
        else: assert False

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, int) or isinstance(other, float): return float(self) == other
        if isinstance(other, str): return str(self).lower() == str(other).lower()
        return str(self) == other
    def __ne__(self, other: Any) -> bool:
        return not (self == other)

    def __gt__(self, other: Any) -> Any:
        return _list_binary_op(self, wrap(other), lambda a, b: _single_cmp(a, b) > 0)
    def __ge__(self, other: Any) -> Any:
        return _list_binary_op(self, wrap(other), lambda a, b: _single_cmp(a, b) >= 0)
    def __lt__(self, other: Any) -> Any:
        return _list_binary_op(self, wrap(other), lambda a, b: _single_cmp(a, b) < 0)
    def __le__(self, other: Any) -> Any:
        return _list_binary_op(self, wrap(other), lambda a, b: _single_cmp(a, b) <= 0)

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

    @property
    def last(self) -> 'Str':
        return wrap(str.__getitem__(self, -1) if len(self) != 0 else '')
    @property
    def rand(self) -> 'Str':
        return wrap(str.__getitem__(self, random.randrange(len(self))) if len(self) != 0 else '')

class List(list):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # these are volatile - we don't persist them on e.g. list concat and they don't count toward size, indexing, etc.
        self.__str_keys = {}

    def __bool__(self) -> bool:
        return True

    def __gt__(self, other: Any) -> Any:
        return _list_binary_op(self, wrap(other), lambda a, b: _single_cmp(a, b) > 0)
    def __ge__(self, other: Any) -> Any:
        return _list_binary_op(self, wrap(other), lambda a, b: _single_cmp(a, b) >= 0)
    def __lt__(self, other: Any) -> Any:
        return _list_binary_op(self, wrap(other), lambda a, b: _single_cmp(a, b) < 0)
    def __le__(self, other: Any) -> Any:
        return _list_binary_op(self, wrap(other), lambda a, b: _single_cmp(a, b) <= 0)

    def __delitem__(self, idx: Any) -> None:
        idx = _parse_index(idx)
        t = type(idx)
        if t is slice: list.__delitem__(self, idx)
        elif t is List: pass
        elif t is str: del self.__str_keys[idx]
        elif t is int:
            if idx < 0: del self.__str_keys[str(idx)]
            elif idx < len(self): list.__delitem__(self, idx)
            else: pass
        else: assert False
    def __getitem__(self, idx: Any) -> Any:
        idx = _parse_index(idx)
        t = type(idx)
        if t is slice: return wrap(list.__getitem__(self, idx))
        elif t is List: return _list_unary_op(wrap(idx), lambda x: self[x])
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
        if t is slice: list.__setitem__(self, idx, value)
        elif t is List: pass
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

    def __iadd__(self, other: Any) -> 'List':
        return self + other

    def append(self, value) -> None:
        list.append(self, wrap(value))
    def insert(self, idx, value) -> None:
        list.insert(self, idx, wrap(value))
    def insert_rand(self, value) -> None:
        list.insert(self, random.randrange(len(self)) if len(self) != 0 else 0, wrap(value))

    @property
    def rand(self) -> Any:
        if len(self) == 0: return wrap('')
        return self[random.randrange(len(self))]
    @rand.setter
    def rand(self, value):
        if len(self) == 0: return
        self[random.randrange(len(self))] = wrap(value)

    @property
    def last(self) -> Any:
        if len(self) == 0: return wrap('')
        return wrap(list.__getitem__(self, -1))
    @last.setter
    def last(self, value):
        if len(self) == 0: return
        list.__setitem__(self, -1, wrap(value))

    def reshaped(self, dims) -> Any:
        dims = wrap(dims)
        if not _is_list(dims):
            dims = wrap([dims])

        raw = []
        for i in range(len(dims)):
            x = +dims[i]
            y = int(x)
            if x != y: raise ValueError(f'reshape dims must be int, got {x}')
            if y < 0: raise ValueError(f'reshape dims cannot be negative, got {y}')
            if y == 0: return wrap([])
            raw.append(y)

        src = self.flat
        if len(src) == 0:
            src = wrap([''])

        i = [0]
        def create(d):
            if len(d) == 0:
                r = src[i[0]]
                i[0] += 1
                if i[0] >= len(src):
                    i[0] = 0
                return r
            else:
                return [create(d[1:]) for _ in range(d[0])]
        return wrap(create(raw))

    @property
    def shape(self) -> 'List':
        res = []
        def visitor(v, depth = 0):
            if depth >= len(res):
                res.append(0)
            res[depth] = max(res[depth], len(v))
            for x in v:
                if _is_list(x):
                    visitor(x, depth + 1)
        visitor(self)
        return wrap(res)
    @property
    def flat(self) -> 'List':
        res = []
        def visitor(v):
            for x in v:
                if _is_list(x):
                    visitor(x)
                else:
                    res.append(x)
        visitor(self)
        return wrap(res)
    @property
    def T(self) -> 'List':
        columns = max([0, *[len(x) if _is_list(x) else 1 for x in self]])
        res = []
        for column in range(columns):
            inner = []
            for row in self:
                inner.append(row[column] if _is_list(row) else row)
            res.append(inner)
        return wrap(res)

    @property
    def csv(self):
        res = io.StringIO()
        writer = csv.writer(res, lineterminator = '')
        if any(_is_list(x) for x in self):
            for i, row in enumerate(self):
                if i != 0: res.write('\n')
                writer.writerow(row)
        else:
            writer.writerow(self)
        return wrap(res.getvalue())

    def pop(self) -> Any:
        if len(self) == 0: return wrap('')
        res = wrap(list.__getitem__(self, -1))
        list.__delitem__(self, -1)
        return res

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

def combinations(*sources: Any) -> Sequence[Any]:
    '''
    Returns a list of combinations of items in the source lists.
    With one list, this returns `[x]` for each `x` in in the list.
    With two lists, this returns `[x, y]` for each `x` and `y` the first and second lists, respectively.
    And so on.
    '''
    sources = wrap(sources)
    if len(sources) == 0: return wrap([])
    return wrap(list(itertools.product(*sources)))

def log(value: Any, base: Any) -> Any:
    return _list_binary_op(wrap(value), wrap(base), lambda x, y: wrap(math.log(+x, +y)))

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

def atan2(y: Any, x: Any) -> Any:
    return _list_binary_op(wrap(y), wrap(x), lambda a, b: wrap(math.atan2(+a, +b) * (180 / math.pi)))

def get_ord(value: Any) -> Any:
    return _list_unary_op(wrap(value), lambda x: wrap(ord(str(x))))
def get_chr(value: Any) -> Any:
    return _list_unary_op(wrap(value), lambda x: wrap(chr(+x)))

def sign(value: Any) -> Any:
    return _list_unary_op(wrap(value), lambda x: wrap(_single_cmp(x, wrap(0))))

def identical(a: Any, b: Any) -> Any:
    a, b = wrap(a), wrap(b)
    la, lb = _is_list(a), _is_list(b)
    if la and lb: return a is b
    if la or lb: return False
    return a == b

def prod(vals: Any) -> Any:
    vals = wrap(vals)
    if type(vals) is List: return _list_fold_op(vals, wrap(1), lambda x, y: x * y)
    else: return vals

def split(src: Any, by: Any) -> List:
    def splitter(x, y):
        x, y = str(x), str(y)
        return wrap(x.split(y) if y != '' else list(x))
    return _list_binary_op(wrap(src), wrap(by), splitter)
def split_csv(src: Any) -> List:
    def splitter(x):
        raw = list(csv.reader(str(x).splitlines()))
        return wrap(raw[0]) if len(raw) == 1 else wrap(raw)
    return _list_unary_op(wrap(src), splitter)
def split_words(src: Any) -> List:
    return _list_unary_op(wrap(src), lambda x: wrap(re.split(r'\s+', str(x))))
def split_json(src: Any) -> List:
    return _list_unary_op(wrap(src), lambda x: wrap(json.loads(str(x))))

def is_number(value: Any) -> bool:
    if isinstance(value, bool): return False
    try:
        +wrap(value)
        return True
    except:
        return False
def is_text(value: Any) -> bool:
    return not isinstance(value, bool) and (isinstance(value, str) or isinstance(value, int) or isinstance(value, float)) and not is_number(value)
def is_bool(value: Any) -> bool:
    return isinstance(value, bool)
def is_list(value: Any) -> bool:
    return isinstance(value, list) or isinstance(value, tuple) or isinstance(value, dict)
def is_sprite(value: Any) -> bool:
    return isinstance(value, _netsblox.graphical.SpriteBase)

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
    assert v[1][0] == 3 and v[1][1] == 4 and v.last[0] == 54 and v.last.last == 3
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
    assert wrap([]).rand == '' and is_wrapped(wrap([]).rand)
    assert wrap([]).last == '' and is_wrapped(wrap([]).last)
    assert wrap([3]).last == 3 and is_wrapped(wrap([3]).last)
    assert wrap([3, 46]).last == 46 and is_wrapped(wrap([3, 46]).last)
    assert wrap([3, 101, 46]).last == 46 and is_wrapped(wrap([3, 101, 46]).last)

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
    vv = v.rand ; assert vv == '' and is_wrapped(vv)
    vv = v[1:] ; assert vv == [] and is_wrapped(vv) and vv is not v and not identical(vv, v)
    v = wrap([7])
    vv = v.rand ; assert vv == 7 and is_wrapped(vv)
    vv = v[1:] ; assert vv == [] and is_wrapped(vv) and vv is not wrap([])[1:]
    v = wrap([3, 6, 3, 8, 7])
    vv = v[1:] ; assert vv == [6, 3, 8, 7] and is_wrapped(vv) and v == [3,6,3,8,7]
    xx = vv.pop() ; assert xx == 7 and is_wrapped(xx) and vv == [6,3,8] and vv.last == 8 and vv.last == 8 and is_wrapped(vv.last)
    xx = vv.pop() ; assert xx == 8 and is_wrapped(xx) and vv == [6,3] and vv.last == 3 and vv.last == 3 and is_wrapped(vv.last)
    xx = vv.pop() ; assert xx == 3 and is_wrapped(xx) and vv == [6] and vv.last == 6 and vv.last == 6 and is_wrapped(vv.last)
    xx = vv.pop() ; assert xx == 6 and is_wrapped(xx) and vv == [] and vv.last == '' and vv.last == '' and is_wrapped(vv.last)
    xx = vv.pop() ; assert xx == '' and is_wrapped(xx) and vv == [] and vv.last == '' and vv.last == '' and is_wrapped(vv.last)
    xx = vv.pop() ; assert xx == '' and is_wrapped(xx) and vv == [] and vv.last == '' and vv.last == '' and is_wrapped(vv.last)
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

    assert prod([4, 2, 6]) == 48 and is_wrapped(prod([4, 2, 6]))
    assert prod([4]) == 4 and is_wrapped(prod([4]))
    assert prod([]) == 1 and is_wrapped(prod([]))
    assert prod([[4, 2, 6], [2, 7, 3]]) == [8, 14, 18] and is_wrapped(prod([[4, 2, 6], [2, 7, 3]]))

    assert (wrap('7') > 4) == True and (wrap('7') > '4') == True and (wrap('7') >= 4) == True and (wrap('7') >= '4') == True
    assert (wrap('7') < 12) == True and (wrap('7') < '12') == True and (wrap('7') <= 12) == True and (wrap('7') <= '12') == True
    assert (wrap('7') == 7) == True and (wrap('7') == '7') == True and (wrap('7') != 12) == True and (wrap('7') != '12') == True
    assert (wrap('7') < 4) == False and (wrap('7') < '4') == False and (wrap('7') <= 4) == False and (wrap('7') <= '4') == False
    assert (wrap('7') > 12) == False and (wrap('7') > '12') == False and (wrap('7') >= 12) == False and (wrap('7') >= '12') == False
    assert (wrap('7') == 12) == False and (wrap('7') == '12') == False and (wrap('7') != 7) == False and (wrap('7') != '7') == False

    assert (wrap(7) > 4) == True and (wrap(7) > '4') == True and (wrap(7) >= 4) == True and (wrap(7) >= '4') == True
    assert (wrap(7) < 12) == True and (wrap(7) < '12') == True and (wrap(7) <= 12) == True and (wrap(7) <= '12') == True
    assert (wrap(7) == 7) == True and (wrap(7) == '7') == True and (wrap(7) != 12) == True and (wrap(7) != '12') == True
    assert (wrap(7) < 4) == False and (wrap(7) < '4') == False and (wrap(7) <= 4) == False and (wrap(7) <= '4') == False
    assert (wrap(7) > 12) == False and (wrap(7) > '12') == False and (wrap(7) >= 12) == False and (wrap(7) >= '12') == False
    assert (wrap(7) == 12) == False and (wrap(7) == '12') == False and (wrap(7) != 7) == False and (wrap(7) != '7') == False

    assert (wrap('7') < [1, 5, 7, 9, 10]) == [False, False, False, True, True]
    assert (wrap('7') <= [1, 5, 7, 9, 10]) == [False, False, True, True, True]
    assert (wrap('7') > [1, 5, 7, 9, 10]) == [True, True, False, False, False]
    assert (wrap('7') >= [1, 5, 7, 9, 10]) == [True, True, True, False, False]
    assert (wrap('7') >= [1, 5, 7, 9, 10]) != [True, True, False, False, False]

    assert (wrap(7) < ['1', 5, 7, 9, 10]) == [False, False, False, True, True]
    assert (wrap(7) <= [1, '5', 7, 9, 10]) == [False, False, True, True, True]
    assert (wrap(7) > [1, 5, '7', 9, 10]) == [True, True, False, False, False]
    assert (wrap(7) >= [1, 5, 7, '9', 10]) == [True, True, True, False, False]
    assert (wrap(7) >= [1, 5, 7, 9, '10']) != [True, True, False, False, False]

    assert (wrap(['1', 5, 7, 9, 10]) > 7) == [False, False, False, True, True]
    assert (wrap([1, '5', 7, 9, 10]) >= 7) == [False, False, True, True, True]
    assert (wrap([1, 5, '7', 9, 10]) < 7) == [True, True, False, False, False]
    assert (wrap([1, 5, 7, '9', 10]) <= 7) == [True, True, True, False, False]
    assert (wrap([1, 5, 7, 9, '10']) <= 7) != [True, True, False, False, False]

    assert (wrap(['1', 5, 7, 9, 10]) > '7') == [False, False, False, True, True]
    assert (wrap([1, '5', 7, 9, 10]) >= '7') == [False, False, True, True, True]
    assert (wrap([1, 5, '7', 9, 10]) < '7') == [True, True, False, False, False]
    assert (wrap([1, 5, 7, '9', 10]) <= '7') == [True, True, True, False, False]
    assert (wrap([1, 5, 7, 9, '10']) <= '7') != [True, True, False, False, False]

    assert sign(6) == 1 and is_wrapped(sign(6))
    assert sign('-7') == -1 and is_wrapped(sign(-7))
    assert sign(0) == 0 and is_wrapped(sign(0))
    assert sign(['5', -2, '0', 3]) == [1, -1, 0, 1] and is_wrapped(sign([5, -2, 0, 3]))

    assert is_wrapped(atan2(1, '2')) and abs(atan2('1', 2) - 26.5650511) < 0.00001
    assert is_wrapped(log(10, '2')) and abs(log('10', 2) - 3.321928) < 0.000001

    assert split('hello world', ' ') == ['hello', 'world']
    assert split('hello  world', ' ') == ['hello', '', 'world']
    assert split(['hello  world', 'again'], ' ') == [['hello', '', 'world'], ['again']]
    assert split('hello world', '') == ['h', 'e', 'l', 'l', 'o', ' ', 'w', 'o', 'r', 'l', 'd']
    assert split(['hello world', 'more'], '') == [['h', 'e', 'l', 'l', 'o', ' ', 'w', 'o', 'r', 'l', 'd'], ['m', 'o', 'r', 'e']]
    assert split('hello\nworld', '\n') == ['hello', 'world']

    assert split_words('hello world') == ['hello', 'world']
    assert split_words('hello  world') == ['hello', 'world']
    assert split_words(['hello world', 'hello    \t \n again']) == [['hello', 'world'], ['hello', 'again']]

    assert split_json('["this", 12, true, "is a", "test"]') == ['this', 12, True, 'is a', 'test']
    assert split_json('{"a": 12, "b": ["x", "y", "z"]}') == [['a', 12], ['b', ['x', 'y', 'z']]]
    assert split_json('{"a": 12, "b": ["x", "y", "z"]}') != [['a', 12], ['b', ['x', 'y', 'zz']]]

    assert split_csv('"this, is some text",12,true,","') == ['this, is some text', '12', 'true', ',']
    assert split_csv('"this, is some text",12,true,","\n12\n\ntrue,') == [['this, is some text', '12', 'true', ','], ['12'], [], ['true', '']]

    assert wrap('z') == wrap('Z') and wrap('aBc') == 'Abc' and 'abC' == wrap('ABC')
    assert wrap({}) == [] and wrap({'a': 5}) == [['a', 5]]

    assert is_number('5') and is_number('-5.8') and is_number(wrap('5')) and is_number(5) and is_number(5.6) and is_number(wrap(5)) and not is_number('hello') and not is_number(wrap('hello')) and not is_number(True) and not is_number([]) and not is_number({})
    assert is_text('hello') and is_text(wrap('hello')) and not is_text(5) and not is_text('5') and not is_text([]) and not is_text(True) and not is_text({})
    assert is_bool(True) and is_bool(False) and is_bool(wrap(True)) and is_bool(wrap(False)) and not is_bool(12) and not is_bool('56') and not is_bool('hello') and not is_bool([]) and not is_bool({})
    assert is_list([]) and is_list({}) and is_list(wrap([])) and is_list(wrap({})) and not is_list('hello') and not is_list(wrap('hello')) and not is_list(45) and not is_list(wrap(45)) and not is_list(True) and not is_list(False) and is_list(())

    v = wrap([1, 5, 3, 8, 6, 4])
    assert v[3] == 8 and v[[2, 4]] == [3, 6] and v[2,[4],2,[[1]]] == [3, [6], 3, [[5]]]

    v = wrap([1, 4, 3])
    vv = wrap([*v])
    assert v == vv and v is not vv
    v = v + 1
    assert v == [2, 5, 4] and vv == [1, 4, 3]
    v += 1
    assert v == [3, 6, 5] and vv == [1, 4, 3]
    v *= 2
    assert v == [6, 12, 10] and vv == [1, 4, 3]
    v /= 2
    assert v == [3, 6, 5] and vv == [1, 4, 3]
    v -= vv
    assert v == [2, 2, 2] and vv == [1, 4, 3]
    v = wrap([1, 2, 3])
    v **= 2
    assert v == [1, 4, 9]

    v = wrap('12')
    v += 5
    assert v == 17
    v += '2'
    assert v == 19

    v = wrap(12)
    v += 5
    assert v == 17
    v += '2'
    assert v == 19

    v = wrap('45')
    v += '12'
    assert v == 57

    v = wrap([1, 3, 4, 2])
    assert v[1:] == [3, 4, 2] and is_wrapped(v[1:])
    assert v.last == 2
    assert wrap([3, 3, 3]).rand == 3
    assert v.index(3) == 1
    assert 3 in v and wrap(3) in v and 5 not in v and wrap(5) not in v
    assert len(v) == 4
    assert v[::-1] == [2, 4, 3, 1] and is_wrapped(v[::-1])
    assert v.shape == [4] and is_wrapped(v.shape)
    assert wrap([4, 3, [], 4]).shape == [4, 0]
    assert wrap([4, 3, [], 4, [6]]).shape == [5, 1]
    assert wrap([4, 3, [[]], 4, [6], [[[]]]]).shape == [6, 1, 1, 0]
    assert wrap([]).shape == [0]
    assert wrap([[]]).shape == [1, 0]

    assert wrap([]).flat == [] and is_wrapped(wrap([]).flat)
    assert wrap([4, 3, 2]).flat == [4, 3, 2] and is_wrapped(wrap([4, 3, 2]).flat)
    assert wrap([4, [[5]], [], [6, [4], 3, 1], 0]).flat == [4, 5, 6, 4, 3, 1, 0]

    assert wrap([[1, 2, 3], [4, 5, 6], [7, 8, 9]]).T == [[1, 4, 7], [2, 5, 8], [3, 6, 9]]
    assert wrap([[1, 2], [4, 5, 6], [7, 8]]).T == [[1, 4, 7], [2, 5, 8], ['', 6, '']]
    assert wrap([[1, 2, 3], [4, 5], [7, 8, 9]]).T == [[1, 4, 7], [2, 5, 8], [3, '', 9]]
    assert wrap([[1, 2], [4, 5], [7, 8, 9]]).T == [[1, 4, 7], [2, 5, 8], ['', '', 9]]
    assert wrap([[1, 2, 3], [4, 5], [7, 8]]).T == [[1, 4, 7], [2, 5, 8], [3, '', '']]
    assert wrap([]).T == [] and wrap([[]]).T == [] and wrap([[]]).shape == [1, 0] and wrap([[]]).T.shape == [0]
    assert wrap([1, 2, 3, 4, 5]).T == [[1, 2, 3, 4, 5]]
    assert wrap([[1,2,3],[4,5],[6]]).T == [[1,4,6],[2,5,''],[3,'','']]
    assert wrap([[1,2,3],[4,5],[6]]).T != [[1,4,6],[2,5],[3]]

    assert wrap([1, 2, 3]).csv == '1,2,3'
    assert wrap([[' ', 2, ' ']]).csv == ' ,2, '
    assert wrap([['some text', 2, 3],[5, 4, 6]]).csv == 'some text,2,3\n5,4,6'
    assert wrap([[1, 2, 3],[5, ',', 6]]).csv == '1,2,3\n5,",",6'

    assert wrap([1, 2, 3])[::-1] == [3, 2, 1] and wrap([4])[::-1] == [4] and wrap([])[::-1] == []

    assert '\n'.join(str(x) for x in [12, 4, 'hello', 'more', 43]) == '12\n4\nhello\nmore\n43'

    v = wrap([])
    v.append(12)
    assert is_wrapped(list.__getitem__(v, 0))
    assert is_wrapped(v[0] is list.__getitem__(v, 0))
    v[0] = 3
    assert is_wrapped(list.__getitem__(v, 0))
    assert is_wrapped(v[0] is list.__getitem__(v, 0))
    v.append('test')
    assert v == [3, 'test']
    v.pop()
    assert v == [3]

    v = wrap([11, 34, 54, 21])
    del v[2]
    assert v == [11, 34, 21]
    vv = v
    assert v is vv
    v.clear()
    assert v is vv and v == [] and vv == []
    v.insert(0, 'test')
    assert v == ['test']
    assert is_wrapped(list.__getitem__(v, 0)) and list.__getitem__(v, 0) is v[0] and v[0] == 'test'
    v.insert(0, 'again')
    assert v == ['again', 'test']
    assert is_wrapped(list.__getitem__(v, 0)) and list.__getitem__(v, 0) is v[0] and v[0] == 'again'

    v = wrap([1, 1, 1])
    v.insert_rand(1)
    assert v == [1, 1, 1, 1] and all(is_wrapped(x) for x in list.__iter__(v))
    v.clear()
    v.insert_rand(12)
    assert v == [12] and all(is_wrapped(x) for x in list.__iter__(v))
    v.rand = 5
    assert v == [5] and all(is_wrapped(x) for x in list.__iter__(v))
    v.rand *= 3
    assert v == [15] and all(is_wrapped(x) for x in list.__iter__(v))
    v = wrap([1, 4, 3])
    assert v.last == 3 and is_wrapped(v.last)
    v.last = 7
    assert v == [1, 4, 7] and v.last == 7 and all(is_wrapped(x) for x in list.__iter__(v))
    v.last += 43
    assert v == [1, 4, 50] and v.last == 50 and all(is_wrapped(x) for x in list.__iter__(v))

    assert wrap([1, 4, 3, 6]).reshaped(2) == [1, 4] and is_wrapped(wrap([1, 4, 3, 6]).reshaped(2))
    assert wrap([1, 4, 5, 2]).reshaped(10) == [1, 4, 5, 2, 1, 4, 5, 2, 1, 4] and is_wrapped(wrap([1, 4, 5, 2]).reshaped(10))
    assert wrap([1, 5]).reshaped([7]) == [1, 5, 1, 5, 1, 5, 1] and is_wrapped(wrap([1, 5]).reshaped([7]))
    assert wrap([1, 7, 2]).reshaped([7, 2]) == [[1, 7], [2, 1], [7, 2], [1, 7], [2, 1], [7, 2], [1, 7]] and is_wrapped(wrap([1, 7, 2]).reshaped([7, 2]))
    assert wrap([1, 7]).reshaped([]) == 1 and is_wrapped(wrap([1, 7]).reshaped([]))
    assert wrap([]).reshaped([3, 2]) == [['', ''], ['', ''], ['', '']] and is_wrapped(wrap([]).reshaped([3, 2]))
    assert wrap([1, 7, 2]).reshaped([1, 1, 7, 2]) == [[[[1, 7], [2, 1], [7, 2], [1, 7], [2, 1], [7, 2], [1, 7]]]] and is_wrapped(wrap([1, 7, 2]).reshaped([1, 1, 7, 2]))
    assert wrap([1, 7, 4]).reshaped([1, 6, 3, 0, 2, 4]) == [] and is_wrapped(wrap([1, 7, 4]).reshaped([1, 6, 3, 0, 2, 4]))
    assert wrap([]).reshaped([2, 2]) == [['', ''], ['', '']] and is_wrapped(wrap([]).reshaped([2, 2]))
    assert wrap([5, 6]).reshaped([]) == 5 and is_wrapped(wrap([5, 6]).reshaped([]))
    assert wrap([5, 6]).reshaped([2, 2, 0, 2]) == []

    v = wrap([[['test']]])
    assert is_wrapped(list.__getitem__(v, 0)) and is_wrapped(list.__getitem__(list.__getitem__(v, 0), 0)) and is_wrapped(list.__getitem__(list.__getitem__(list.__getitem__(v, 0), 0), 0))

    assert combinations() == [] and is_wrapped(combinations())
    assert combinations([1, 2]) == [[1], [2]] and is_wrapped(combinations([1, 2]))
    assert combinations([1, 2], [3, 4]) == [[1, 3], [1, 4], [2, 3], [2, 4]] and is_wrapped(combinations([1, 2], [3, 4]))
    assert combinations([1, 2], [], [3, 4]) == [] and is_wrapped(combinations([1, 2], [3, 4]))

    v = wrap('hello world')
    assert v[0] == 'h' and is_wrapped(v[0]) and v['0'] == 'h' and is_wrapped(v['0'])
    assert v[4] == 'o' and is_wrapped(v[4]) and v['4'] == 'o' and is_wrapped(v['4'])

    assert wrap('').last == '' and is_wrapped(wrap('').last)
    assert wrap('begin').last == 'n' and is_wrapped(wrap('begin').last)
    assert wrap('also').last == 'o' and is_wrapped(wrap('also').last)

    assert wrap('').rand == '' and is_wrapped(wrap('').rand)
    assert wrap('tttt').rand == 't' and is_wrapped(wrap('tttt').rand)

    assert wrap([]).last == '' and is_wrapped(wrap([]).last)
    assert wrap([]).rand == '' and is_wrapped(wrap([]).rand)

    print('passed all snap wrapper tests')
