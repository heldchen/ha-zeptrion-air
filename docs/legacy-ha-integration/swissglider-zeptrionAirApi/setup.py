"""
A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='zeptrionAirApi',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    version='1.2.0.0',
    description="This are the Classes to use the Zeptrion Air Lights etc.",
    long_description=long_description,
    author="Swissglider",
    author_email="swissglider@mailschweiz.com",
    url="https://github.com/swissglider/zeptrionAirApi",
    keywords="zeptrion zeptrion-air Light-Switch Switch Blind-Switch",
    install_requires=['requests', 'zeroconf', 'websockets', 'asyncio'],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    setup_requires=['pytest-runner', 'pylint'],
    tests_require=['pytest', 'pytest-asyncio'],
)
