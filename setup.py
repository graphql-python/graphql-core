from re import search
from setuptools import setup, find_packages

with open("src/graphql/version.py") as version_file:
    version = search('version = "(.*)"', version_file.read()).group(1)

with open("README.md") as readme_file:
    readme = readme_file.read()

setup(
    name="GraphQL-core-next",
    version=version,
    description="GraphQL-core-next is a Python port of GraphQL.js,"
    " the JavaScript reference implementation for GraphQL.",
    long_description=readme,
    long_description_content_type="text/markdown",
    keywords="graphql",
    url="https://github.com/graphql-python/graphql-core-next",
    author="Christoph Zwerschke",
    author_email="cito@online.de",
    license="MIT license",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    install_requires=[],
    python_requires=">=3.6,<4",
    packages=find_packages("src"),
    package_dir={"": "src"},
    # PEP-561: https://www.python.org/dev/peps/pep-0561/
    package_data={"graphql": ["py.typed"]},
    include_package_data=True,
    zip_safe=False,
)
