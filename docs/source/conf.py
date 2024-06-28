# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
sys.path.insert(0, os.path.abspath('../..'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'sartopo_python'
copyright = '2024, Tom Grundy'
author = 'Tom Grundy'
release = '2.0.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
	'sphinx.ext.autodoc'
]

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_logo = '_static/caltopo_python_logo.png'
html_theme_options = {
	'page_width':'80%',
	# 'sidebar_width':'20%',
	'sidebar_collapse':True,
	'fixed_sidebar':True,
	'logo':'caltopo_python_logo.png'
}
html_static_path = ['_static']
html_sidebars = {
	'**': [
		'allpages.html',
		'localtoc.html',
		'searchbox.html'
	]
}

autoclass_content = 'both'
add_module_names = False
toc_object_entries_show_parents = 'hide'
