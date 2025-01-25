#
# GraphQL-core 3 documentation build configuration file, created by
# sphinx-quickstart on Thu Jun 21 16:28:30 2018.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))

# -- General configuration ------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = ".rst"

# The encoding of source files.
#
# source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = "index"

# General information about the project.
project = "GraphQL-core 3"
copyright = "2025, Christoph Zwerschke"
author = "Christoph Zwerschke"

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
# version = '3.3'
# The full version, including alpha/beta/rc tags.
version = release = "3.3.0a6"

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = "en"

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#
# today = ''
#
# Else, today_fmt is used as the format for a strftime call.
#
# today_fmt = '%B %d, %Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# AutoDoc configuration
autoclass_content = "class"
autodoc_default_options = {
    "members": True,
    "inherited-members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
autosummary_generate = True

autodoc_type_aliases = {
    "AwaitableOrValue": "graphql.pyutils.AwaitableOrValue",
    "FormattedSourceLocation": "graphql.language.FormattedSourceLocation",
    "Middleware": "graphql.execution.Middleware",
    "TypeMap": "graphql.schema.TypeMap",
}

# GraphQL-core top level modules with submodules that can be omitted.
# Sometimes autodoc cannot find classes since it is looking for the
# qualified form, but the documentation has the shorter form.
# We need to give autodoc a little help in this cases.
graphql_modules = {
    "error": ["graphql_error"],
    "execution": ["execute", "middleware"],
    "language": [
        "ast",
        "directive_locations",
        "location",
        "source",
        "token_kind",
        "visitor",
    ],
    "pyutils": ["simple_pub_sub", "frozen_list", "path"],
    "type": ["definition", "directives", "schema"],
    "utilities": ["find_breaking_changes", "type_info"],
    "validation": ["rules", "validation_context"],
}

# GraphQL-core classes that autodoc sometimes cannot find
# (e.g. where specified as string in type hints).
# We need to give autodoc a little help in this cases, too:
graphql_classes = {
    "GraphQLAbstractType": "type",
    "GraphQLFieldResolver": "type",
    "GraphQLObjectType": "type",
    "GraphQLOutputType": "type",
    "GraphQLTypeResolver": "type",
    "AwaitableOrValue": "execution",
    "Middleware": "execution",
    "Node": "language",
    "Source": "language",
    "SourceLocation": "language",
}

# ignore the following undocumented or internal references:
ignore_references = set(
    """
GNT GT KT T VT
TContext
enum.Enum
traceback
types.TracebackType
TypeMap
AwaitableOrValue
DeferredFragmentRecord
DeferUsage
EnterLeaveVisitor
ExperimentalIncrementalExecutionResults
FieldGroup
FormattedIncrementalResult
FormattedPendingResult
FormattedSourceLocation
GraphQLAbstractType
GraphQLCompositeType
GraphQLErrorExtensions
GraphQLFieldResolver
GraphQLInputType
GraphQLNullableType
GraphQLOutputType
GraphQLTypeResolver
GroupedFieldSet
IncrementalDataRecord
IncrementalResult
InitialResultRecord
Middleware
PendingResult
StreamItemsRecord
StreamRecord
SubsequentDataRecord
asyncio.events.AbstractEventLoop
collections.abc.MutableMapping
collections.abc.MutableSet
graphql.execution.collect_fields.DeferUsage
graphql.execution.collect_fields.CollectFieldsResult
graphql.execution.collect_fields.FieldGroup
graphql.execution.execute.StreamArguments
graphql.execution.execute.StreamUsage
graphql.execution.map_async_iterable.map_async_iterable
graphql.execution.incremental_publisher.CompletedResult
graphql.execution.incremental_publisher.DeferredFragmentRecord
graphql.execution.incremental_publisher.DeferredGroupedFieldSetRecord
graphql.execution.incremental_publisher.FormattedCompletedResult
graphql.execution.incremental_publisher.FormattedPendingResult
graphql.execution.incremental_publisher.IncrementalPublisher
graphql.execution.incremental_publisher.InitialResultRecord
graphql.execution.incremental_publisher.PendingResult
graphql.execution.incremental_publisher.StreamItemsRecord
graphql.execution.incremental_publisher.StreamRecord
graphql.execution.Middleware
graphql.language.lexer.EscapeSequence
graphql.language.visitor.EnterLeaveVisitor
graphql.pyutils.ref_map.K
graphql.pyutils.ref_map.V
graphql.type.definition.GT_co
graphql.type.definition.GNT_co
graphql.type.definition.TContext
graphql.type.schema.InterfaceImplementations
graphql.validation.validation_context.VariableUsage
graphql.validation.rules.known_argument_names.KnownArgumentNamesOnDirectivesRule
graphql.validation.rules.provided_required_arguments.ProvidedRequiredArgumentsOnDirectivesRule
""".split()
)

ignore_references.update(__builtins__.keys())


def on_missing_reference(app, env, node, contnode):
    """Fix or skip any missing references."""
    if node.get("refdomain") != "py":
        return None
    target = node.get("reftarget")
    if not target:
        return None
    if target in ignore_references or target.endswith("Kwargs"):
        return contnode
    typ = node.get("reftype")
    name = target.rsplit(".", 1)[-1]
    if name in ("GT", "GNT", "KT", "T", "VT"):
        return contnode
    if typ == "obj":
        if target.startswith("typing."):
            if name in ("Any", "Optional", "Union"):
                return contnode
    if typ != "class":
        return None
    if "." in target:  # maybe too specific
        base_module, target = target.split(".", 1)
        if base_module == "graphql":
            if "." not in target:
                return None
            base_module, target = target.split(".", 1)
        if "." not in target:
            return None
        sub_modules = graphql_modules.get(base_module)
        if not sub_modules:
            return None
        sub_module = target.split(".", 1)[0]
        if sub_module not in sub_modules:
            return None
        target = "graphql." + base_module + "." + target.rsplit(".", 1)[-1]
    else:  # maybe not specific enough
        base_module = graphql_classes.get(target)
        if not base_module:
            return None
        target = "graphql." + base_module + "." + target
    # replace target
    if contnode.__class__.__name__ == "Text":
        contnode = contnode.__class__(target)
    elif contnode.__class__.__name__ == "literal":
        if len(contnode.children) != 1:
            return None
        textnode = contnode.children[0]
        contnode.children[0] = textnode.__class__(target)
    else:
        return None
    node["reftarget"] = target
    fromdoc = node.get("refdoc")
    if not fromdoc:
        doc_module = node.get("py:module")
        if doc_module:
            if doc_module.startswith("graphql."):
                doc_module = doc_module.split(".", 1)[-1]
            if doc_module not in graphql_modules and doc_module != "graphql":
                doc_module = None
        fromdoc = "modules/" + (doc_module or base_module)
    # try resolving again with replaced target
    return env.domains["py"].resolve_xref(
        env, fromdoc, app.builder, typ, target, node, contnode
    )


def on_skip_member(_app, what, name, _obj, skip, _options):
    if what == "class" and name == "__init__":
        # we could set "special-members" to "__init__",
        # but this gives an error when documenting modules
        return False
    return skip


def setup(app):
    app.connect("missing-reference", on_missing_reference)
    app.connect("autodoc-skip-member", on_skip_member)


# be nitpicky (handle all possible problems in on_missing_reference)
nitpicky = True


# The reST default role (used for this markup: `text`) to use for all
# documents.
#
# default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
#
# add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
#
# add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#
# show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# A list of ignored prefixes for module index sorting.
# modindex_common_prefix = []

# If true, keep warnings as "system message" paragraphs in the built documents.
# keep_warnings = False

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False

# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
html_theme_options = {"navigation_depth": 5}

# Add any paths that contain custom themes here, relative to this directory.
# html_theme_path = []

# The name for this set of Sphinx documents.
# "<project> v<release> documentation" by default.
#
# html_title = 'GraphQL-core v3.1.0'

# A shorter title for the navigation bar.  Default is the same as html_title.
#
# html_short_title = None

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
#
# html_logo = None

# The name of an image file (relative to this directory) to use as a favicon of
# the docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
#
# html_favicon = None

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']

# Add any extra paths that contain custom files (such as robots.txt or
# .htaccess) here, relative to this directory. These files are copied
# directly to the root of the documentation.
#
# html_extra_path = []

# If not None, a 'Last updated on:' timestamp is inserted at every page
# bottom, using the given strftime format.
# The empty string is equivalent to '%b %d, %Y'.
#
# html_last_updated_fmt = None

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
#
# html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
#
# html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
#
# html_additional_pages = {}

# If false, no module index is generated.
#
# html_domain_indices = True

# If false, no index is generated.
#
# html_use_index = True

# If true, the index is split into individual pages for each letter.
#
# html_split_index = False

# If true, links to the reST sources are added to the pages.
#
html_show_sourcelink = False

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
#
# html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
#
# html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#
# html_use_opensearch = ''

# This is the file name suffix for HTML files (e.g. ".xhtml").
# html_file_suffix = None

# Language to be used for generating the HTML full-text search index.
# Sphinx supports the following languages:
#   'da', 'de', 'en', 'es', 'fi', 'fr', 'hu', 'it', 'ja'
#   'nl', 'no', 'pt', 'ro', 'ru', 'sv', 'tr', 'zh'
#
# html_search_language = 'en'

# A dictionary with options for the search language support, empty by default.
# 'ja' uses this config value.
# 'zh' user can custom change `jieba` dictionary path.
#
# html_search_options = {'type': 'default'}

# The name of a javascript file (relative to the configuration directory) that
# implements a search results scorer. If empty, the default will be used.
#
# html_search_scorer = 'scorer.js'

# Output file base name for HTML help builder.
htmlhelp_basename = "GraphQL-core-3-doc"

# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',
    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',
    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',
    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (
        master_doc,
        "GraphQL-core-3.tex",
        "GraphQL-core 3 Documentation",
        "Christoph Zwerschke",
        "manual",
    ),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
#
# latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#
# latex_use_parts = False

# If true, show page references after internal links.
#
# latex_show_pagerefs = False

# If true, show URL addresses after external links.
#
# latex_show_urls = False

# Documents to append as an appendix to all manuals.
#
# latex_appendices = []

# If false, no module index is generated.
#
# latex_domain_indices = True


# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [(master_doc, "graphql-core", "GraphQL-core 3 Documentation", [author], 1)]

# If true, show URL addresses after external links.
#
# man_show_urls = False


# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "GraphQL-core",
        "GraphQL-core 3 Documentation",
        author,
        "GraphQL-core 3",
        "One line description of project.",
        "Miscellaneous",
    ),
]

# Documents to append as an appendix to all manuals.
#
# texinfo_appendices = []

# If false, no module index is generated.
#
# texinfo_domain_indices = True

# How to display URL addresses: 'footnote', 'no', or 'inline'.
#
# texinfo_show_urls = 'footnote'

# If true, do not generate a @detailmenu in the "Top" node's menu.
#
# texinfo_no_detailmenu = False
