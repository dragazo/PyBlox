#!/usr/bin/env python

from typing import Any, List

import parso # docs: https://parso.readthedocs.io/_/downloads/en/latest/pdf/
import unittest

def remove_new_line(line: str) -> str:
    if line.endswith('\r\n'):
        return line[:-2]
    if line.endswith('\n'):
        return line[:-1]
    return line

def inclusive_splitlines(src: str) -> List[str]:
    res = src.splitlines()
    if src and src[-1] == '\n':
        res.append('')
    return res

def add_to_pos(lines: List[str], res: List[str], res_pos: List[int], target_pos: int) -> None:
    assert target_pos >= res_pos[0]
    for i in range(res_pos[0], target_pos):
        res.append(f'{lines[i]}\n' if i < len(lines) - 1 else lines[i])
    res_pos[0] = target_pos

def line_span(node):
    start_line = node.start_pos[0]
    end_line = node.end_pos[0] - 1 if node.end_pos[1] == 0 else node.end_pos[0]
    return start_line, end_line

def add_breaks_recursive(node: Any, lines: List[str], res: List[str], res_pos: List[int]) -> None:
    if hasattr(node, 'children'):
        for child in node.children:
            add_breaks_recursive(child, lines, res, res_pos)

    if node.type == 'while_stmt':
        if len(node.children) >= 3 and node.children[0] == 'while' and node.children[2] == ':':
            cnd = node.children[1]
            cnd_start, cnd_end = line_span(cnd)
            colon_line, colon_col = node.children[2].end_pos

            add_to_pos(lines, res, res_pos, cnd_start - 1)
            res.append(f'while _yield_({cnd.get_code(include_prefix = False)}):{lines[colon_line - 1][colon_col:]}\n')
            res_pos[0] = cnd_end
    elif node.type == 'for_stmt':
        if len(node.children) >= 5 and node.children[0] == 'for' and node.children[2] == 'in' and node.children[4] == ':':
            var = node.children[1]
            vals = node.children[3]
            colon_line, colon_col = node.children[4].end_pos

            add_to_pos(lines, res, res_pos, line_span(node.children[0])[0] - 1)
            res.append(f'for {var.get_code(include_prefix = False)} in map(_yield_, {vals.get_code(include_prefix = False)}):{lines[colon_line - 1][colon_col:]}\n')
            res_pos[0] = colon_line

def add_breaks(code: str) -> str:
    root = parso.parse(code)
    lines = [remove_new_line(x) for x in inclusive_splitlines(code)]
    res = []
    res_pos = [0]
    add_breaks_recursive(root, lines, res, res_pos)
    add_to_pos(lines, res, res_pos, len(lines))
    return ''.join(res)

class AddBreaksTests(unittest.TestCase):
    def test_simple_for(self):
        res = add_breaks('''
while flag or other_flag: # some comment
    foo(i ** 2)
    bar(i, i + 2)
'''.strip())
        self.assertEqual(res, '''
while _yield_(flag or other_flag): # some comment
    foo(i ** 2)
    bar(i, i + 2)
'''.strip())

    def test_simple_for_ws(self):
        res = add_breaks('''
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

    def test_simple_for(self):
        res = add_breaks('''
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
        res = add_breaks('''
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


def test():
    assert '하나 둘 셋 넷'[0] == '하' # sanity check: str indexing is char based
    assert '하나 둘 셋 넷'[1] == '나'
    assert '하나 둘 셋 넷'[2] == ' '
    assert '하나 둘 셋 넷'[3] == '둘'

    for  i,   \
      j\
          in \
               enumerate(\
                    [1, 2,\
           3]
     )\
                 :
        print(i, j)

    unittest.main()

# --------------------------------------------------------------------------

if __name__ == '__main__':
    test()
