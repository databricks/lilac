"""Configuration for sphinx."""
# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Lilac'
copyright = '2023, Lilac AI Inc.'
author = 'Lilac AI Inc.'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
  'sphinx.ext.autodoc',
  'sphinx.ext.coverage',
  'sphinx.ext.autodoc.typehints',
  'sphinx.ext.autosummary',
  'sphinxcontrib.autodoc_pydantic',
  'myst_parser',
]

autodoc_pydantic_model_show_json = False
autodoc_pydantic_field_list_validators = False
autodoc_pydantic_config_members = False
autodoc_pydantic_model_show_field_summary = False
autodoc_pydantic_model_show_config_summary = False
autodoc_pydantic_model_show_validator_members = False
autodoc_pydantic_model_show_validator_summary = False
autodoc_pydantic_model_signature_prefix = 'class'
autodoc_pydantic_field_signature_prefix = 'param'
autodoc_typehints_format = 'short'

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', '.venv', 'README.md']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']
html_css_files = [
  'styles/custom.css',
]
