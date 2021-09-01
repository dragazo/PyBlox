#!/usr/bin/env python

from typing import Tuple, Any, List

import parso # docs: https://parso.readthedocs.io/_/downloads/en/latest/pdf/
import unittest

def remove_new_line(line: str):
    if line.endswith('\r\n'):
        return line[:-2]
    if line.endswith('\n'):
        return line[:-1]
    return line

def get_indent(line: str) -> str:
    content = line.lstrip()
    return line[:len(line) - len(content)]

def inclusive_splitlines(src: str) -> List[str]:
    res = src.splitlines()
    if src and src[-1] == '\n':
        res.append('')
    return res

def add_to_pos(lines: List[str], res: List[str], res_pos: List[int], target_pos: int) -> None:
    assert target_pos >= res_pos[0]
    for i in range(res_pos[0], target_pos):
        res.append(lines[i])
    res_pos[0] = target_pos

def trim_newline_nodes(nodes: List[Any]) -> List[Any]:
    i = 0
    while i < len(nodes) and nodes[i].type == 'newline':
        i += 1
    j = len(nodes)
    while j > i and nodes[j - 1].type == 'newline':
        j -= 1
    return nodes[i:j]

def line_span(node):
    start_line = node.start_pos[0]
    end_line = node.end_pos[0] - 1 if node.end_pos[1] == 0 else node.end_pos[0]
    return start_line, end_line

def add_breaks_recursive(node: Any, lines: List[str], line_indents: List[str], res: List[str], res_pos: List[int], added_lines: List[int]) -> None:
    if hasattr(node, 'children'):
        for child in node.children:
            add_breaks_recursive(child, lines, line_indents, res, res_pos, added_lines)

    if node.type in ['while_stmt', 'for_stmt']:
        stmts = trim_newline_nodes(node.children[-1].children)
        last_begin, last_end = line_span(stmts[-1])

        add_to_pos(lines, res, res_pos, last_end)
        res.append(f'{line_indents[last_begin - 1]}time.sleep(0)')
        added_lines.append(last_end + 1)

def add_breaks(code: str) -> Tuple[str, List[int]]:
    root = parso.parse(code)
    lines = [remove_new_line(x) for x in inclusive_splitlines(code)]
    line_indents = [get_indent(x) for x in lines]
    res = []
    res_pos = [0]
    added_lines = []
    add_breaks_recursive(root, lines, line_indents, res, res_pos, added_lines)
    add_to_pos(lines, res, res_pos, len(lines))
    return '\n'.join(res), added_lines

class AddBreaksTests(unittest.TestCase):
    def test_short_loop(self):
        res, added = add_breaks('''
for i in range(10):
    print(x)
'''.strip())
        self.assertEqual(res, '''
for i in range(10):
    print(x)
    time.sleep(0)
'''.strip())
        self.assertEqual(added, [3])
    
    def test_short_loop_ws(self):
        res, added = add_breaks('''
for i in range(10):
    print(x)
''')
        self.assertEqual(res, '''
for i in range(10):
    print(x)
    time.sleep(0)
''')
        self.assertEqual(added, [4])

    def test_longer_loop(self):
        res, added = add_breaks('''
for i in range(10):
    x = i ** i
    print(x)
'''.strip())
        self.assertEqual(res, '''
for i in range(10):
    x = i ** i
    print(x)
    time.sleep(0)
'''.strip())
        self.assertEqual(added, [4])
    
    def test_longer_loop_ws(self):
        res, added = add_breaks('''

for i in range(10):
    x = i ** i

    print(x)

''')
        self.assertEqual(res, '''

for i in range(10):
    x = i ** i

    print(x)
    time.sleep(0)

''')
        self.assertEqual(added, [7])
    
    def test_multi_short_loops(self):
        res, added = add_breaks('''
for i in range(10):
    print(x)
for i in range(10):
    print(x)
for i in range(10):
    print(x)
'''.strip())
        self.assertEqual(res, '''
for i in range(10):
    print(x)
    time.sleep(0)
for i in range(10):
    print(x)
    time.sleep(0)
for i in range(10):
    print(x)
    time.sleep(0)
'''.strip())
        self.assertEqual(added, [3, 5, 7])
    
    def test_multi_short_loops_ws(self):
        res, added = add_breaks('''
for i in range(10):

        # some comment

    print(x)
for i in range(10):
    print(x)

for i in range(10):

    print(x)

''')
        self.assertEqual(res, '''
for i in range(10):

        # some comment

    print(x)
    time.sleep(0)
for i in range(10):
    print(x)
    time.sleep(0)

for i in range(10):

    print(x)
    time.sleep(0)

''')
        self.assertEqual(added, [7, 9, 13])

    def test_ws_comment(self):
        res, added = add_breaks('''
for i in range(10):

  # something

    pass

      # else thing

''')
        self.assertEqual(res, '''
for i in range(10):

  # something

    pass
    time.sleep(0)

      # else thing

''')
        self.assertEqual(added, [7])

    def test_multi_line_last_stmt(self):
        res, added = add_breaks('''
for i in range(10):
  
    print(
        x
            )
''')
        self.assertEqual(res, '''
for i in range(10):
  
    print(
        x
            )
    time.sleep(0)
''')
        self.assertEqual(added, [7])

    def test_multi_line_last_stmt_while(self):
        res, added = add_breaks('''
while cond:
  
    print(
        x
            )
''')
        self.assertEqual(res, '''
while cond:
  
    print(
        x
            )
    time.sleep(0)
''')
        self.assertEqual(added, [7])
    
    def test_loop_error_1(self):
        res, added = add_breaks('''
for i in range(10):
''')
        self.assertEqual(res, '''
for i in range(10):
''')
        self.assertEqual(added, [])
    
    def test_loop_error_2(self):
        res, added = add_breaks('''
for i in range(10):
    # merp derp
''')
        self.assertEqual(res, '''
for i in range(10):
    # merp derp
''')
        self.assertEqual(added, [])
    
    def test_expr_loop_end(self):
        res, added = add_breaks('''
for i in range(10):
    6
''')
        self.assertEqual(res, '''
for i in range(10):
    6
    time.sleep(0)
''')
        self.assertEqual(added, [4])
    
    def test_loop_error_2(self):
        res, added = add_breaks('''
for i in range(10):
pass
''')
        self.assertEqual(res, '''
for i in range(10):
pass
''')
        self.assertEqual(added, [])

    def test_nested_loops(self):
        res, added = add_breaks('''
for i in range(10):
    pass
for j in range(10):
    for k in range(6):
        pass # hello world
for x in range(10):
    pass
'''.strip())
        self.assertEqual(res, '''
for i in range(10):
    pass
    time.sleep(0)
for j in range(10):
    for k in range(6):
        pass # hello world
        time.sleep(0)
    time.sleep(0)
for x in range(10):
    pass
    time.sleep(0)
'''.strip())
        self.assertEqual(added, [3, 6, 6, 8])

def test():
    assert '하나 둘 셋 넷'[0] == '하' # sanity check: str indexing is char based
    assert '하나 둘 셋 넷'[1] == '나'
    assert '하나 둘 셋 넷'[2] == ' '
    assert '하나 둘 셋 넷'[3] == '둘'

    unittest.main()

# --------------------------------------------------------------------------

if __name__ == '__main__':
    test()
