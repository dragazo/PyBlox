#!/usr/bin/env python

import tkinter as tk
from tkinter import ttk
import multiprocessing as mproc
import subprocess
import threading
import traceback
import turtle
import sys
import io
import re

from typing import List, Tuple

import netsblox

from . import turtle as nbturtle
from . import transform

color_enabled = False
try:
    # idle gives us syntax highlighting, but we don't require it otherwise
    import idlelib.colorizer as colorizer
    import idlelib.percolator as percolator
    color_enabled = True
except:
    pass

force_enabled = False
try:
    import jedi
    force_enabled = True
except:
    pass

root = None
toolbar = None
content = None

_print_queue = mproc.Queue(maxsize = 256)
_print_batchsize = 256
_print_targets = []
def _process_print_queue():
    for _ in range(_print_batchsize):
        if _print_queue.empty():
            break
        val = _print_queue.get()
        for target in _print_targets:
            try:
                target.write(val)
            except:
                pass # throwing would break print queue
    root.after(33, _process_print_queue)

def get_white_nonwhite(line: str) -> Tuple[str, str]:
    i = 0
    while i < len(line) and line[i].isspace():
        i += 1
    return line[:i], line[i:]
def undent_single(line: str) -> str:
    i = 0
    while i < 4 and i < len(line) and line[i].isspace():
        i += 1
    return line[i:], i # remove at most 4 whitespace chars

def indent(txt: str) -> str:
    return '\n'.join([ f'    {x}' for x in txt.splitlines() ])
def indent_info(txt: str) -> str:
    indents = [ f'    {x}' for x in txt.splitlines() ]
    return '\n'.join(indents), [4 for _ in indents]
def undent_info(txt: str) -> Tuple[str, int, int]:
    undents = [ undent_single(x) for x in txt.splitlines() ]
    if len(undents) == 0:
        return txt, 0, 0
    return '\n'.join([ x[0] for x in undents ]), [ -x[1] for x in undents ]

def smart_comment_uncomment(txt: str) -> Tuple[str, int]:
    line_parts = [ get_white_nonwhite(x) for x in txt.splitlines() ]
    should_uncomment = all(part[1].startswith('#') or part[1] == '' for part in line_parts)

    if should_uncomment:
        res_lines = []
        res_deltas = []
        for part in line_parts:
            for prefix in ['# ', '#', '']:
                if part[1].startswith(prefix):
                    res_lines.append(part[0] + part[1][len(prefix):])
                    res_deltas.append(-len(prefix))
                    break
        return '\n'.join(res_lines), res_deltas
    else:
        res_lines = []
        res_deltas = []
        for part in line_parts:
            if part[1] != '':
                res_lines.append(f'{part[0]}# {part[1]}')
                res_deltas.append(2)
            else:
                res_lines.append(part[0] + part[1])
                res_deltas.append(0)
        return '\n'.join(res_lines), res_deltas

def exec_wrapper(*args):
    try:
        exec(*args)
    except:
        print(traceback.format_exc(), file = sys.stderr) # print out directly so that the stdio wrappers are used

_exec_process = None
def play_button():
    global _exec_process

    # if already running, just kill it - the only locks they can have were made by them, so no deadlocking issues.
    # the messaging pipe is broken, but we won't be using it anymore.
    if _exec_process is not None:
        _exec_process.terminate()
        _exec_process = None
        toolbar.run_button.show_play()
        return

    toolbar.run_button.show_stop()

    # wipe whatever was on the display
    content.display.turtle_disp.screen.clear()
    content.display.terminal.text.set_text('')
    nbturtle._new_game()

    # the first turtle on a blank screen for some reason clears click/key events,
    # so make an invisible turtle and then reset the click events
    turtle.RawTurtle(content.display.turtle_disp.canvas, visible = False)
    content.display.turtle_disp.screen.onclick(content.display.turtle_disp.screen.listen)

    def file_piper(src, dst):
        src = io.TextIOWrapper(src)
        for c in iter(lambda: src.read(1), ''):
            dst.write(c)
            dst.flush()

    code = content.project.get_full_script()
    _exec_process = subprocess.Popen([sys.executable, '-uc', code], stdout = subprocess.PIPE, stderr = subprocess.PIPE)

    # reading the pipes is blocking so do in another thread for each stream - they will exit when process is killed
    threading.Thread(target = file_piper, args = (_exec_process.stdout, sys.stdout), daemon = True).start()
    threading.Thread(target = file_piper, args = (_exec_process.stderr, sys.stderr), daemon = True).start()

_package_dir = netsblox.__path__[0]
def module_path(path: str) -> str:
    return f'{_package_dir}/{path}'

class Toolbar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(side = tk.TOP, fill = tk.X)

        self.run_button = StartStopButton(self, command = play_button)
        self.run_button.pack()

class StartStopButton(tk.Button):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, width = 5, **kwargs)
        self.show_play()

    def show_play(self):
        self.config(text = '▶', bg = '#2d9e29', fg = 'white')
    def show_stop(self):
        self.config(text = '■', bg = '#b31515', fg = 'white')

class Content(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(side = tk.BOTTOM, fill = tk.BOTH, expand = True)

        self.project = ProjectEditor(self)
        self.display = Display(self)

        self.project.grid(row = 0, column = 0, sticky = tk.NSEW)
        self.display.grid(row = 0, column = 1, sticky = tk.NSEW)

        self.grid_columnconfigure(0, weight = 4, uniform = 'content')
        self.grid_columnconfigure(1, weight = 3, uniform = 'content')
        self.grid_rowconfigure(0, weight = 1)

class DndTarget:
    def __init__(self, widget, on_start, on_stop, on_drop):
        self.widget = widget
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_drop = on_drop

class DndManager:
    def __init__(self, widget, targets: List[DndTarget]):
        self.targets = targets

        widget.bind('<ButtonPress-1>', self.on_start)
        widget.bind('<B1-Motion>', self.on_drag)
        widget.bind('<ButtonRelease-1>', self.on_drop)
        widget.configure(cursor = 'hand1')
    
    def on_start(self, e):
        for target in self.targets:
            target.on_start(e)

    def on_drag(self, e):
        pass

    def on_drop(self, e):
        for target in self.targets:
            target.on_stop(e)

        x, y = e.widget.winfo_pointerxy()
        dest_widget = e.widget.winfo_containing(x, y)
        for target in self.targets:
            if dest_widget is target.widget:
                target.on_drop(e)
                break

class BlocksList(tk.Frame):
    def __init__(self, parent, blocks, text_target):
        super().__init__(parent)

        self.scrollbar = tk.Scrollbar(self)
        self.text = tk.Text(self, wrap = tk.NONE, width = 16, yscrollcommand = self.scrollbar.set)
        self.scrollbar.configure(command = self.text.yview)

        self.scrollbar.pack(side = tk.RIGHT, fill = tk.Y)
        self.text.pack(side = tk.LEFT, fill = tk.Y, expand = True)

        orig_bcolor = text_target.cget('background')
        def make_dnd_manager(widget, code):
            def on_start(e):
                text_target.configure(highlightbackground = 'red')
                pass
            def on_stop(e):
                text_target.configure(highlightbackground = orig_bcolor)
                pass
            def on_drop(e):
                x, y = text_target.winfo_pointerxy()
                x -= text_target.winfo_rootx()
                y -= text_target.winfo_rooty()

                pos = text_target.index(f'@{x},{y}')
                text_target.insert(f'{pos} linestart', f'{code}\n')
                text_target.edit_separator() # so multiple drag and drops aren't undone as one

                return 'break'

            return DndManager(widget, [DndTarget(text_target, on_start, on_stop, on_drop)])

        self.imgs = [] # for some reason we need to keep a reference to the images or they disappear
        for img_path, code in blocks:
            img = tk.PhotoImage(file = module_path(img_path))
            label = tk.Label(self, image = img)

            self.text.window_create('end', window = label)
            self.text.insert('end', '\n')
            self.imgs.append(img)

            make_dnd_manager(label, code)

        self.text.configure(state = tk.DISABLED)

class ProjectEditor(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.turtle_index = 0
        self.editors = []

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill = tk.BOTH, expand = True)

        def on_change(e):
            for _, editor in self.editors:
                editor.hide_suggestion()
            tab = e.widget.tab('current')['text']
            editors = [x[1] for x in self.editors if x[0] == tab]
            assert len(editors) == 1
            editors[0].on_content_change(e)
        self.notebook.bind('<<NotebookTabChanged>>', on_change)

        editor = GlobalEditor(self.notebook)
        self.notebook.add(editor, text = 'global')
        self.editors.append(('global', editor))

        editor = StageEditor(self.notebook, 'stage')
        self.notebook.add(editor, text = editor.name)
        self.editors.append((editor.name, editor))

        self.newturtle('turtle')

    def newturtle(self, name = None):
        if name is None:
            self.turtle_index += 1
            name = f'turtle{self.turtle_index}'
        
        if not any(x[0] == name for x in self.editors):
            editor = TurtleEditor(self.notebook, name)
            self.notebook.add(editor, text = name)
            self.editors.append((name, editor))
    
    def get_full_script(self):
        scripts = []
        for _, editor in self.editors:
            scripts.append(editor.get_script())
            scripts.append('\n\n')
        scripts.append('start_project()')
        return ''.join(scripts)

# source: https://stackoverflow.com/questions/16369470/tkinter-adding-line-number-to-text-widget
class TextLineNumbers(tk.Canvas):
    def __init__(self, parent, *, target, width):
        super().__init__(parent, width = width)
        self.width = width
        self.textwidget = target
        self.line_num_offset = 0

    def redraw(self):
        self.delete('all')

        i = self.textwidget.index('@0,0')
        while True:
            dline = self.textwidget.dlineinfo(i)
            if dline is None:
                break

            y = dline[1]
            linenum = int(str(i).split('.')[0]) + self.line_num_offset
            self.create_text(self.width - 2, y, anchor = 'ne', text = str(linenum))
            i = self.textwidget.index(f'{i}+1line')

# source: https://stackoverflow.com/questions/16369470/tkinter-adding-line-number-to-text-widget
class ChangedText(tk.Text):
    __name_id = 0

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        # create a proxy for the underlying widget
        ChangedText.__name_id += 1
        self._orig = self._w + f'_orig_{ChangedText.__name_id}'
        self.tk.call('rename', self._w, self._orig)
        self.tk.createcommand(self._w, self._proxy)

    def _proxy(self, *args):
        # let the actual widget perform the requested action
        cmd = (self._orig, *args)
        result = None
        try:
            result = self.tk.call(cmd)
        except Exception as e:
            # for some reason our proxying breaks undo/redo if the stacks are empty, so just catch and ignore
            if cmd[1:] not in [('edit', 'undo'), ('edit', 'redo')]:
                raise e

        # generate an event if something was added or deleted, or the cursor position changed
        changed = args[0] in ('insert', 'replace', 'delete') or \
            args[0:3] == ('mark', 'set', 'insert') or \
            args[0:2] == ('xview', 'moveto') or \
            args[0:2] == ('xview', 'scroll') or \
            args[0:2] == ('yview', 'moveto') or \
            args[0:2] == ('yview', 'scroll')
        if changed:
            self.event_generate('<<Change>>', when = 'tail')

        return result # return what the actual widget returned

class ScrolledText(tk.Frame):
    def __init__(self, parent, *, readonly = False, linenumbers = False, blocks = []):
        super().__init__(parent)
        undo_args = { 'undo': True, 'maxundo': -1, 'autoseparators': True }

        self.scrollbar = tk.Scrollbar(self)
        self.text = ChangedText(self, yscrollcommand = self.scrollbar.set, **({} if readonly else undo_args))
        self.scrollbar.config(command = self.text.yview)

        self.custom_on_change = []

        def on_select_all(e):
            self.text.tag_add(tk.SEL, '1.0', tk.END)
            return 'break'
        self.text.bind('<Control-Key-a>', on_select_all)
        self.text.bind('<Control-Key-A>', on_select_all)

        self.linenumbers = None # default to none - conditionally created
        self.blocks = None

        if readonly:
            # make text readonly be ignoring all (default) keystrokes
            self.text.bind('<Key>', lambda e: 'break')

            # catching all keys above means we can't copy anymore - impl manually
            def on_copy(e):
                self.clipboard_clear()
                self.clipboard_append(self.text.selection_get())
                return 'break'
            self.text.bind('<Control-Key-c>', on_copy)
            self.text.bind('<Control-Key-C>', on_copy)
        else:
            def on_redo(e):
                self.text.edit_redo()
                return 'break'
            self.text.bind('<Control-Key-y>', on_redo)
            self.text.bind('<Control-Key-Y>', on_redo)
        
        if linenumbers:
            self.linenumbers = TextLineNumbers(self, target = self.text, width = 30)
            self.text.bind('<<Change>>', self.on_content_change)
            self.text.bind('<Configure>', self.on_content_change)
        
        if len(blocks) > 0:
            self.blocks = BlocksList(self, blocks, self.text)

        # -----------------------------------------------------

        self.scrollbar.pack(side = tk.RIGHT, fill = tk.Y)
        if len(blocks) > 0:
            self.blocks.pack(side = tk.LEFT, fill = tk.Y)
        if linenumbers:
            self.linenumbers.pack(side = tk.LEFT, fill = tk.Y)
        self.text.pack(side = tk.RIGHT, fill = tk.BOTH, expand = True)

    def on_content_change(self, e):
        for handler in self.custom_on_change:
            handler(e)
        if self.linenumbers is not None:
            self.linenumbers.redraw()

    def set_text(self, txt):
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', txt)

class CodeEditor(ScrolledText):
    def __init__(self, parent, *, column_offset = 0, **kwargs):
        super().__init__(parent, linenumbers = True, **kwargs)
        self.__line_count = None
        self.column_offset = column_offset
        self.help_popup = None

        def on_change(e):
            self.__line_count = None
            if content is not None:
                total = 0
                for _, editor in content.project.editors:
                    if editor is self:
                        total += editor.prefix_lines
                        break
                    total += editor.line_count() + 1
                self.linenumbers.line_num_offset = total
        self.custom_on_change.append(on_change)

        self.text.bind('<Shift-Key-Tab>', lambda e: self.do_untab())
        self.text.bind('<Shift-ISO_Left_Tab>', lambda e: self.do_untab()) # needed on linux, for some reason

        self.text.bind('<Control-slash>', lambda e: self.do_autocomment())

        self.text.bind('<Tab>', lambda e: self.do_tab())
        self.text.bind('<BackSpace>', lambda e: self.do_backspace())

        if color_enabled:
            # source: https://stackoverflow.com/questions/38594978/tkinter-syntax-highlighting-for-text-widget
            cdg = colorizer.ColorDelegator()

            patterns = [
                r'(?P<MYDECO>@\w+)\b',
                r'\b(?P<MYSELF>self)\b',
                r'\b(?P<MYNUMBER>(\d+\.?|\.\d)\d*(e[-+]?\d+)?)\b',
                colorizer.make_pat(),
            ]
            cdg.prog = re.compile('|'.join(patterns))

            cdg.tagdefs['COMMENT']    = {'foreground': '#a3a3a3', 'background': '#ffffff'}
            cdg.tagdefs['MYNUMBER']   = {'foreground': '#c26910', 'background': '#ffffff'}
            cdg.tagdefs['MYSELF']     = {'foreground': '#a023a6', 'background': '#ffffff'}
            cdg.tagdefs['BUILTIN']    = {'foreground': '#6414b5', 'background': '#ffffff'}
            cdg.tagdefs['DEFINITION'] = {'foreground': '#6414b5', 'background': '#ffffff'}
            cdg.tagdefs['MYDECO']     = {'foreground': '#6414b5', 'background': '#ffffff'}
            cdg.tagdefs['KEYWORD']    = {'foreground': '#0d15b8', 'background': '#ffffff'}
            cdg.tagdefs['STRING']     = {'foreground': '#961a1a', 'background': '#ffffff'}

            percolator.Percolator(self.text).insertfilter(cdg)

        if force_enabled:
            self.custom_on_change.append(lambda e: self.show_full_help())
            self.text.bind('<Control-Key-space>', lambda e: self.show_suggestion())

    def line_count(self):
        if self.__line_count:
            return self.__line_count
        content = self.get_script() # defined by base classes
        self.__line_count = content.count('\n') + 1
        return self.__line_count

    def show_full_help(self):
        if not force_enabled or content is None or content.project is None:
            return
        script = jedi.Script(content.project.get_full_script())
        self.update_highlighting(script)

        should_show = \
            self.text.get('insert - 1 chars', 'insert').startswith('.') or \
            self.text.get('insert - 1 chars wordstart - 1 chars', 'insert').startswith('.')

        if should_show and not self.text.tag_ranges(tk.SEL):
            self.show_suggestion(script)
        else:
            self.hide_suggestion()

    def update_highlighting(self, script = None):
        if not force_enabled or content is None or content.project is None:
            return
        if script is None:
            script = jedi.Script(content.project.get_full_script())

        self.text.tag_delete('jedi-syntax-err')
        for err in script.get_syntax_errors():
            start = f'{err.line       - self.linenumbers.line_num_offset}.{err.column       - self.column_offset}'
            stop  = f'{err.until_line - self.linenumbers.line_num_offset}.{err.until_column - self.column_offset}'
            self.text.tag_add('jedi-syntax-err', start, stop)
        self.text.tag_configure('jedi-syntax-err', underline = True, underlinefg = 'red', background = '#f2a5a5', foreground = 'black')

    def show_suggestion(self, script = None):
        if not force_enabled or content is None or content.project is None:
            return
        if script is None:
            script = jedi.Script(content.project.get_full_script())

        edit_line, edit_col = map(int, self.text.index(tk.INSERT).split('.'))
        edit_line += self.linenumbers.line_num_offset
        edit_col += self.column_offset
        completions = script.complete(edit_line, edit_col)

        should_show = len(completions) >= 2 or (len(completions) == 1 and completions[0].complete != '')
        if should_show:
            if self.help_popup is not None:
                self.help_popup.destroy()
            x, y, w, h = self.text.bbox(tk.INSERT)
            self.help_popup = tk.Listbox()
            self.help_completions = {}

            xoff = self.text.winfo_rootx() - root.winfo_rootx()
            yoff = self.text.winfo_rooty() - root.winfo_rooty()
            self.help_popup.place(x = x + xoff, y = y + yoff + h)
            for item in completions:
                if not item.name.startswith('_'): # hide private stuff - would only confuse beginners and they shouldn't touch it anyway
                    self.help_popup.insert(tk.END, item.name)
                    self.help_completions[item.name] = item.complete
            
            self.help_popup.bind('<Double-Button-1>', lambda e: self.do_completion())
        else:
            self.hide_suggestion()

    def do_completion(self):
        if self.help_popup is not None:
            completion = self.help_completions[self.help_popup.get(tk.ACTIVE)]
            self.text.insert(tk.INSERT, completion)
        self.text.focus_set()

    def hide_suggestion(self):
        if self.help_popup is not None:
            self.help_popup.destroy()
            self.help_popup = None

    def _do_batch_edit(self, mutator):
        ins = self.text.index(tk.INSERT)
        sel_start, sel_end = self.text.index(tk.SEL_FIRST), self.text.index(tk.SEL_LAST)
        sel_padded = f'{sel_start} linestart', f'{sel_end} lineend'

        ins_pieces = ins.split('.')
        sel_start_pieces, sel_end_pieces = sel_start.split('.'), sel_end.split('.')

        content = self.text.get(*sel_padded)
        mutated, line_deltas = mutator(content)
        ins_delta = line_deltas[int(ins_pieces[0]) - int(sel_start_pieces[0])]

        self.text.edit_separator()
        self.text.delete(*sel_padded)
        self.text.insert(sel_padded[0], mutated)
        self.text.edit_separator()
        
        new_sel_start = f'{sel_start_pieces[0]}.{max(0, int(sel_start_pieces[1]) + line_deltas[0])}'
        new_sel_end = f'{sel_end_pieces[0]}.{max(0, int(sel_end_pieces[1]) + line_deltas[-1])}'
        new_ins = f'{ins_pieces[0]}.{max(0, int(ins_pieces[1]) + ins_delta)}'

        self.text.tag_add(tk.SEL, new_sel_start, new_sel_end)
        self.text.mark_set(tk.INSERT, new_ins)

    def do_backspace(self):
        col = int(self.text.index(tk.INSERT).split('.')[1])
        if col != 0:
            del_count = (col % 4) or 4 # delete back to previous tab column
            pos = f'insert - {del_count} chars'
            if self.text.get(pos, 'insert').isspace():
                self.text.delete(pos, 'insert')
                return 'break' # override default behavior
    def do_untab(self):
        if self.text.tag_ranges(tk.SEL):
            self._do_batch_edit(undent_info)

        return 'break'
    def do_tab(self):
        if self.text.tag_ranges(tk.SEL):
            self._do_batch_edit(indent_info)
        elif self.help_popup is not None:
            self.do_completion()
        else:
            self.text.insert(tk.INSERT, '    ')

        return 'break' # we always override default (we don't want tabs ever)
    
    def do_autocomment(self):
        if self.text.tag_ranges(tk.SEL):
            self._do_batch_edit(smart_comment_uncomment)
        
        return 'break'

class GlobalEditor(CodeEditor):
    prefix = '''
import netsblox
nb = netsblox.Client()
from netsblox.turtle import *
from netsblox.concurrency import *
setup_yielding()
import time
def _yield_(x):
    time.sleep(0)
    return x

'''.lstrip()
    prefix_lines = 10

    blocks = [
        ('img/onstart.png', '@onstart\ndef function_name():\n    pass'),
        ('img/sleep.png', 'time.sleep(1)'),
    ]

    def __init__(self, parent):
        super().__init__(parent, blocks = GlobalEditor.blocks)

        self.set_text('''
someval = 'hello world' # create a global variable
'''.strip())

    def get_script(self):
        return transform.add_yields(self.prefix + self.text.get('1.0', 'end-1c'))

class StageEditor(CodeEditor):
    prefix_lines = 2

    def __init__(self, parent, name):
        super().__init__(parent, column_offset = 4) # we autoindent the content, so 4 offset for error messages
        self.name = name

        self.set_text('''
@onstart
def start(self):
    self.myvar = 5                 # create a stage variable
    print('value is:', self.myvar) # access stage variable

    for i in range(10):
        print(i ** 2)
'''.strip())

    def get_script(self):
        raw = self.text.get('1.0', 'end-1c')
        return transform.add_yields(f'@stage\nclass {self.name}(StageBase):\n{indent(raw)}\n{self.name} = {self.name}()')

class TurtleEditor(CodeEditor):
    prefix_lines = 2

    def __init__(self, parent, name):
        super().__init__(parent, column_offset = 4) # we autoindent the content, so 4 offset for error messages
        self.name = name

        self.set_text('''
@onstart
def start(self):
    self.myvar = 40 # create a sprite variable

    for i in range(400):
        self.forward(self.myvar) # access sprite variable
        self.right(90)
'''.strip())

    def get_script(self):
        raw = self.text.get('1.0', 'end-1c')
        return transform.add_yields(f'@turtle\nclass {self.name}(TurtleBase):\n{indent(raw)}\n{self.name} = {self.name}()')

class Display(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.turtle_disp = TurtleDisplay(self)
        self.terminal = TerminalOutput(self)

        self.turtle_disp.grid(row = 0, column = 0, sticky = tk.NSEW)
        self.terminal.grid(row = 1, column = 0, sticky = tk.NSEW)

        self.grid_columnconfigure(0, weight = 1)
        self.grid_rowconfigure(0, weight = 1, uniform = 'display')
        self.grid_rowconfigure(1, weight = 1, uniform = 'display')

class TerminalOutput(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        def style(control):
            control.config(bg = '#1a1a1a', fg = '#bdbdbd', insertbackground = '#bdbdbd')

        self.entry = tk.Entry(self)
        self.entry.pack(side = tk.BOTTOM, fill = tk.X)
        style(self.entry)

        self.text = ScrolledText(self, readonly = True)
        self.text.pack(side = tk.TOP, fill = tk.BOTH, expand = True)
        style(self.text.text)

    def wrap_stdio(self, *, tee: bool):
        _print_targets.append(self)

        class TeeWriter:
            encoding = 'utf-8'

            def __init__(self, old):
                self.old = old

            def write(self, data):
                data = str(data)
                if self.old is not None:
                    self.old.write(data)
                    self.old.flush()
                _print_queue.put(data)
            
            def flush(self):
                pass
            def __len__(self):
                return 0

        sys.stdout = TeeWriter(sys.stdout if tee else None)
        sys.stderr = TeeWriter(sys.stderr if tee else None)
    
    def write(self, txt):
        self.text.text.insert('end', str(txt))
        self.text.text.see(tk.END)
    def write_line(self, txt):
        self.write(f'{txt}\n')

class TurtleDisplay(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.canvas = turtle.ScrolledCanvas(self)
        self.canvas.pack(fill = tk.BOTH, expand = True)

        self.screen = turtle.TurtleScreen(self.canvas)

        # ScrolledCanvas has better behavior, but we dont actually want scrollbars, so always match display size
        self.canvas.bind('<Configure>', lambda e: self.screen.screensize(canvwidth = e.width, canvheight = e.height))

def main():
    global root, toolbar, content

    root = tk.Tk()
    root.geometry('1200x600')
    root.minsize(width = 800, height = 400)
    root.title('NetsBlox - Python')
    ttk.Style().theme_use('clam')

    toolbar = Toolbar(root)
    content = Content(root)

    content.display.terminal.wrap_stdio(tee = True)

    _process_print_queue()
    root.mainloop()

if __name__ == '__main__':
    main()
