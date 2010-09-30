#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='cxm',
	version='0.5.1',
	license='GPLv3',
	description='Clustered Xen Management API and tools',
	author='Nicolas Agius',
	url='http://github.com/nagius/cxm',
	author_email='nagius@astek.fr',
	package_dir={'': 'lib'},
	packages=find_packages('lib'),
	test_suite='nose.collector',
	test_requires=['Nose'],
)

