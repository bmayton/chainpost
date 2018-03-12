#!/usr/bin/env python

from setuptools import setup

setup(
    name='chainpost',
    version='0.4',
    description='A wrapper to make posting with chainclient easier',
    py_modules=['chainpost'],
    author='Brian Mayton',
    author_email='bmayton@media.mit.edu',
    url='http://bdm.cc',
    license='MIT',
    install_requires=['chainclient >= 0.4.0'],
)
