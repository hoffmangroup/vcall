#!/usr/bin/env python

"""vcall: DESCRIPTION

LONG_DESCRIPTION
"""

__version__ = "0.1.0a1"

# Copyright 2008, 2013 Michael M. Hoffman <hoffman@cantab.net>

from ez_setup import use_setuptools
use_setuptools()

from setuptools import setup

doclines = __doc__.splitlines()
name, short_description = doclines[0].split(": ")
long_description = "\n".join(doclines[2:])

url = "http://www.ebi.ac.uk/~hoffman/software/%s/" % name.lower()
download_url = "%s%s-%s.tar.gz" % (url, name, __version__)

classifiers = ["License :: OSI Approved :: GNU General Public License (GPL)",
               "Natural Language :: English",
               "Programming Language :: Python"]

setup(name=name,
      version=__version__,
      description=short_description,
      author="Michael Hoffman",
      author_email="hoffman@cantab.net",
      url=url,
      download_url=download_url,
      license="GNU GPLv2",
      classifiers=classifiers,
      long_description=long_description,
      zip_safe=True,
      scripts=["scripts/vcall"])
