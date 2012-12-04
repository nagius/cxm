# -*- coding:Utf-8 -*-

# cxm - Clustered Xen Management API and tools
# Copyleft 2011-2012 - Nicolas AGIUS <nicolas.agius@lps-it.fr>
# $Id:$

###########################################################################
#
# This file is part of cxm.
#
# cxm is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###########################################################################

import logs as log
import os, time
try:
	import cPickle as pickle
except:
	import pickle

class PersistentCache(object):
	
	def __init__(self, file, ttl=60, timeout=15):
		"""
		This class is a decorator that save the return value of functions even
		after the interpreter dies. This cache is stored in a file, so it could 
		be shared between many instance of the same script that run in parallel.
		A lock is used to prevent simultaneous write of this cache. 

		Values returned by the decorated function are serialized with cPickle.

		Parameters :
		 
		- file    : filename of the cache. Should be in a writable path.
		- ttl     : life time of the cached datas (in seconds)
		- timeout : maximum time (in seconds) to wait for the release of the lock. 
		If excedeed, the lock is deleted and the function is called to feed the cache.
		
		Example of usage :

		>>> @PersistentCache("/some/were/myfilecache", ttl=5, timeout=10)
		>>> def myfunc(param):
		>>> 	return param

		>>> myfunc("some parameters")
			# Will call myfunc and feed the cache
		>>> myfunc("some parameters")
			# Will not call myfunc but read the cache

		Be carefull, there is a (small) bug :
		>>> myfunc("other parameters")
			# Will hit the cache and return the value with the previous parameters
		"""

		assert type(file) == str, "'file' should be a string."
		self.file=file
		self.lock=file + ".lock"

		assert type(ttl) == int, "'ttl' should be an integer."
		self.ttl=ttl

		assert type(timeout) == int, "'timeout' should be an integer."
		self.timeout=timeout

	def _read_cache(self):
		try:
			f=open(self.file, 'r')
			try:
				data=pickle.load(f)
			except Exception, e:
				# Python simplicity in example : Pickle raise just one ... sorry, 
				# Pickle could raise more than 7 exceptions in case of bad input file...
				# So we have to catch all of them and re-raise a single exception.
				raise pickle.PickleError(e)
			f.close()

			mtime=os.stat(self.file).st_mtime
			if(int(time.time()) - mtime > self.ttl):
				log.debug("[PCH]", "EXPIRED", self.file)
				raise InvalidCacheException("Cache expired")
			else:
				log.debug("[PCH]", "HIT", self.file)
				return data

		except (IOError, OSError, pickle.PickleError):
			log.debug("[PCH]", "MISS", self.file)
			raise InvalidCacheException("Missing or bad cache file")

	def _lock_cache(self):
		open(self.lock, 'w').close()

	def _write_cache(self, data):
		f=open(self.file,'w')
		pickle.dump(data, f)
		f.close()
		
	def _unlock_cache(self):
		if os.path.exists(self.lock):
			os.unlink(self.lock)

	def _is_cache_locked(self):
		try:
			mtime=os.stat(self.lock).st_mtime
			if(int(time.time()) - mtime > self.timeout):
				log.debug("[PCH]", "LOCK TIMEOUT", self.lock)
				raise TimeoutException()
			else:
				return True
		except OSError:
			return False

	def __call__(self, callback):
		def cache(*args, **kw):
			try:
				# Wait for lock to be released or timeout
				while self._is_cache_locked():
					time.sleep(1)			

				# No lock or lock released
				return self._read_cache()

			except (InvalidCacheException, TimeoutException):
				self._lock_cache()
				value=callback(*args, **kw)
				self._write_cache(value)
				self._unlock_cache()
				return value
		return cache


class TimeoutException(Exception):
	"""Raised when the lock is too old."""
	pass

class InvalidCacheException(Exception):
	"""Raised when the cache is invalid or outdated."""
	pass

# vim: ts=4:sw=4:ai
