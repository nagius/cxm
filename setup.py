#!/usr/bin/env python

from setuptools import setup, find_packages
from cxm import meta

setup(name=meta.name,
	version=meta.version,
	license=meta.license,
	description=meta.description,
	author=meta.authors,
	url=meta.url,
	author_email=meta.authors_email,
	package_dir={'': 'lib'},
	packages=find_packages('lib'),
	test_suite='nose.collector',
	test_requires=['Nose'],
)

