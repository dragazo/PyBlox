#!/usr/bin/env python

from typing import Any, List

import parso # docs: https://parso.readthedocs.io/_/downloads/en/latest/pdf/
import unittest

import netsblox.common as common

def remove_new_line(line: str) -> str:
    if line.endswith('\r\n'):
        return line[:-2]
    if line.endswith('\n'):
        return line[:-1]
    return line

def trailing_indent(txt: str) -> str:
    i = len(txt)
    while i > 0:
        ch = txt[i - 1]
        if ch == '\n' or not ch.isspace():
            return txt[i:]
        i -= 1
    return txt

def remove_leading_ws(txt: str) -> str:
    for i, ch in enumerate(txt):
        if ch == '\n' or not ch.isspace():
            return txt[i:]
    return ''

def add_to_pos(lines: List[str], res: List[str], res_pos: List[int], target_pos: int) -> None:
    assert target_pos >= res_pos[0]
    for i in range(res_pos[0], target_pos):
        res.append(f'{lines[i]}\n' if i < len(lines) - 1 else lines[i])
    res_pos[0] = target_pos
def adv_to_pos(res_pos: List[int], target_pos: int) -> None:
    assert target_pos >= res_pos[0]
    res_pos[0] = target_pos

def line_span(node):
    start_line = node.start_pos[0]
    end_line = node.end_pos[0] - 1 if node.end_pos[1] == 0 else node.end_pos[0]
    return start_line, end_line

def add_yields_recursive(node: Any, lines: List[str], res: List[str], res_pos: List[int]) -> None:
    if node.type == 'while_stmt':
        if len(node.children) >= 3 and node.children[0] == 'while' and node.children[2] == ':':
            while_tok, cnd, colon_tok = node.children[:3]

            while_line = while_tok.start_pos[0]
            colon_line, colon_col = colon_tok.end_pos

            while_code = while_tok.get_code()
            assert while_code.endswith('while')
            while_code = trailing_indent(while_code[:-5]) + 'while'

            cnd_code = remove_leading_ws(cnd.get_code())
            colon_code = colon_tok.get_code()

            add_to_pos(lines, res, res_pos, while_line - 1)
            res.append(f'{while_code} _yield_({cnd_code}){colon_code}{lines[colon_line - 1][colon_col:]}\n')
            adv_to_pos(res_pos, colon_line)
    elif node.type == 'for_stmt':
        if len(node.children) >= 5 and node.children[0] == 'for' and node.children[2] == 'in' and node.children[4] == ':':
            for_tok, vars, in_tok, vals, colon_tok = node.children[:5]
            
            for_line = for_tok.start_pos[0]
            colon_line, colon_col = colon_tok.end_pos

            for_code = for_tok.get_code()
            assert for_code.endswith('for')
            for_code = trailing_indent(for_code[:-3]) + 'for'

            vars_code = vars.get_code()
            in_code = in_tok.get_code()
            vals_code = remove_leading_ws(vals.get_code())
            colon_code = colon_tok.get_code()

            add_to_pos(lines, res, res_pos, for_line - 1)
            res.append(f'{for_code}{vars_code}{in_code} map(_yield_, {vals_code}){colon_code}{lines[colon_line - 1][colon_col:]}\n')
            adv_to_pos(res_pos, colon_line)
    
    if hasattr(node, 'children'):
        for child in node.children:
            add_yields_recursive(child, lines, res, res_pos)

def add_yields(code: str) -> str:
    '''
    Injects calls to `_yield_` before each iteration of a while or for loop.
    `_yield_` is expected to already be defined.
    '''

    root = parso.parse(code)
    lines = [remove_new_line(x) for x in common.inclusive_splitlines(code)]
    res = []
    res_pos = [0]
    add_yields_recursive(root, lines, res, res_pos)
    add_to_pos(lines, res, res_pos, len(lines))
    return ''.join(res)

class AddBreaksTests(unittest.TestCase):
    def test_simple_while(self):
        res = add_yields('''
while flag or other_flag: # some comment
    foo(i ** 2)
    bar(i, i + 2)
'''.strip())
        self.assertEqual(res, '''
while _yield_(flag or other_flag): # some comment
    foo(i ** 2)
    bar(i, i + 2)
'''.strip())

    def test_simple_while_ws(self):
        res = add_yields('''
    # another comment
while flag or other_flag: # some comment
    foo(i ** 2)
    bar(i, i + 2)
''')
        self.assertEqual(res, '''
    # another comment
while _yield_(flag or other_flag): # some comment
    foo(i ** 2)
    bar(i, i + 2)
''')

    def test_nested_while_ws(self):
        res = add_yields('''
    # another comment
while flag: # some comment
    while not other_flag: # another comment
        foo(i ** 2)
        bar(i, i + 2)
    bazz(i)
''')
        self.assertEqual(res, '''
    # another comment
while _yield_(flag): # some comment
    while _yield_(not other_flag): # another comment
        foo(i ** 2)
        bar(i, i + 2)
    bazz(i)
''')

    def test_cursed_while_loops(self):
        res = add_yields('''
i = 0
while   \\
  i < \\
   6\\
 :

    print(i)

    j = 0
    while   \\
  j < \\
                          8\\
     : print(j); j += 1 # some comment

    i += 1
''')
        self.assertEqual(res, '''
i = 0
while _yield_(\\
  i < \\
   6)\\
 :

    print(i)

    j = 0
    while _yield_(\\
  j < \\
                          8)\\
     : print(j); j += 1 # some comment

    i += 1
''')

    def test_simple_for(self):
        res = add_yields('''
for i in vals: # some comment
    foo(i ** 2)
    bar(i, i + 2)
'''.strip())
        self.assertEqual(res, '''
for i in map(_yield_, vals): # some comment
    foo(i ** 2)
    bar(i, i + 2)
'''.strip())

    def test_simple_for_ws(self):
        res = add_yields('''
      # another comment
for i, val in enumerate(vals + [1, 2, 3] + other): # some comment
    foo(i ** 2)
    bar(i, i + 2)
''')
        self.assertEqual(res, '''
      # another comment
for i, val in map(_yield_, enumerate(vals + [1, 2, 3] + other)): # some comment
    foo(i ** 2)
    bar(i, i + 2)
''')

    def test_cursed_for_loops(self):
        res = add_yields('''
for \\
i,   \\
   j\\
       in \\
         enumerate( # saying something inspiring
              [1, 2,
  3] # another test
      ) \\
                : # test comment
        bar(i,
            j)
        for \\
    i,   \\
            j\\
          in \\
                enumerate( # something else
                    [1, 2,
            37] # another test
        ) \\
                    : # test comment
            foo(\\
                i, j
      )
''')
        self.assertEqual(res, '''
for \\
i,   \\
   j\\
       in map(_yield_, \\
         enumerate( # saying something inspiring
              [1, 2,
  3] # another test
      )) \\
                : # test comment
        bar(i,
            j)
        for \\
    i,   \\
            j\\
          in map(_yield_, \\
                enumerate( # something else
                    [1, 2,
            37] # another test
        )) \\
                    : # test comment
            foo(\\
                i, j
      )
''')
    def test_in_func(self):
        res = add_yields('''
def foo(x, y, z):
    for i in range(10):
        while x[i] and z[y[i]]:
            foo(bar)
''')
        self.assertEqual(res, '''
def foo(x, y, z):
    for i in map(_yield_, range(10)):
        while _yield_(x[i] and z[y[i]]):
            foo(bar)
''')
    def test_in_method(self):
        res = add_yields('''
class MyClass:
    def foo(self, x, y, z):
        for i in range(10):
            while x[i] and z[y[i]]:
                foo(bar)
''')
        self.assertEqual(res, '''
class MyClass:
    def foo(self, x, y, z):
        for i in map(_yield_, range(10)):
            while _yield_(x[i] and z[y[i]]):
                foo(bar)
''')

def test():
    assert '하나 둘 셋 넷'[0] == '하' # sanity check: str indexing is char based
    assert '하나 둘 셋 넷'[1] == '나'
    assert '하나 둘 셋 넷'[2] == ' '
    assert '하나 둘 셋 넷'[3] == '둘'

    unittest.main()

if __name__ == '__main__':
    test()
