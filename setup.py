#!/usr/bin/env python

from setuptools import setup, find_packages
from cxm import meta

author, author_email = meta.authors[0]

setup(name=meta.name,
	version=meta.version,
	license=meta.license,
	description=meta.description,
	author=author,
	url=meta.url,
	author_email=author_email,
	package_dir={'': 'lib'},
	packages=find_packages('lib'),
	test_suite='nose.collector',
	test_requires=['Nose'],
)

