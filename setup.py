#!/usr/bin/env python

# Copyright 2008, 2013, 2016, 2020 Michael M. Hoffman <hoffman@cantab.net>

from setuptools import setup

classifiers = ["License :: OSI Approved :: GNU General Public License (GPL)",
               "Natural Language :: English",
               "Programming Language :: Python"]

setup(name='vcall',
      version='0.1.0a3',
      description='execute version control commands for many directories',
      author='Michael Hoffman',
      author_email='michael.hoffman@utoronto.ca',
      license='GPLv3',
      classifiers=classifiers,
      package_data={"vcall": ["py.typed"]},
      packages=['vcall'],
      python_requires='>=3.6',
      install_requires=["optbuild", "tqdm"],
      extras_require={'gui': ["matplotlib"]},
      entry_points={
        'console_scripts': ['vcall=vcall.__main__:main'],
      },
      zip_safe=False)
