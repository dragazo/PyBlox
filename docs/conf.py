# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import os
import sys

sys.path.insert(0, '.')

# -- Building ----------------------------------------------------------------

DOCS_PATH = os.getcwd()
try:
    os.chdir('..')
    import build # our build module in root directory
    build.main_sync()
finally:
    os.chdir(DOCS_PATH)

# -- Markdown conversions ----------------------------------------------------

import commonmark

def docstring(app, what, name, obj, options, lines):
    md  = '\n'.join(lines)
    ast = commonmark.Parser().parse(md)
    rst = commonmark.ReStructuredTextRenderer().render(ast)

    temp = [x.rstrip() for x in rst.splitlines()]
    def is_section_title(i):
        if i + 1 >= len(temp): return False
        curr_line = temp[i]
        next_line = temp[i + 1]
        if len(curr_line) == 0 or len(next_line) != len(curr_line): return False
        if next_line[0] not in ['-', '=', '*', '^']: return False
        if any(next_line[i] != next_line[0] for i in range(1, len(next_line))): return False
        return True

    res = []
    pos = 0
    while pos < len(temp):
        if is_section_title(pos):
            res.append(f'**{temp[pos]}**')
            pos += 2
        else:
            res.append(temp[pos])
            pos += 1

    lines.clear()
    lines += res

def setup(app):
    app.connect('autodoc-process-docstring', docstring)

# -- Project information -----------------------------------------------------

project = 'NetsBlox-python'
copyright = '2021 Vanderbilt University'
author = 'Devin Jean'

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']
