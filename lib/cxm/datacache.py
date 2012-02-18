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

import time
import logs as log

class DataCache(object):
	
	"""This class is a cache for any type of data with a small lifetime."""

	def __init__(self):
		self._data = dict()

	def add(self, key, lifetime, value): 
		"""
		Add a new value to the cache.
		 - 'key' could be any hashable object, but a significant string is better,
		 - 'lifetime' is in second,
		 - 'value' could be an object or any type.
		"""
		self._data[key] = {
				'expire': int(time.time())+lifetime,
				'value': value
			}
		log.debug("[CAH]", "ADD", key, lifetime, value)

	def get(self, key):
		"""
		Return the cached value of the specified key.
		If the value is outdated, it will be deleted from cache and a CacheExpiredException 
		will be raised.
		If the key is unknown, a CacheMissingException will be raised.
		"""
		try:
			data=self._data[key]
		except KeyError:
			log.debug("[CAH]", "MISS", key)
			raise CacheMissingException(key)

		if data['expire'] <= int(time.time()):
			self.delete(key)
			raise CacheExpiredException(key)

		log.debug("[CAH]", "HIT", key, data['value'])
		return data['value']
			
	def delete(self, key):
		"""Delete the value associated with the key."""
		try:
			del self._data[key]
			log.debug("[CAH]", "DEL", key)
		except KeyError:
			pass
		
	def clear(self):
		"""Clear the cache: erase all datas."""
		self._data.clear()
		log.debug("[CAH]", "Cleared")

	def cleanup(self):
		"""Delete outdated values."""
		for key, data in self._data.items():
			if data['expire'] <= int(time.time()):
				self.delete(key)

	def cache(self, lifetime, nocache, callback, *args, **kw):
		"""
		Return the cached result of the callback.

		If the result is not in the cache or is outdated, the callback will 
		be run and the new value put in cache for 'lifetime' seconds.
		If 'nocache' is True, the cache is only feeded.
		"""

		try:
			if nocache:
				raise CacheException
			else:
				return self.get(callback.__name__)
		except CacheException:
			value = callback(*args, **kw)
			self.add(callback.__name__, lifetime, value)
			return value


class CacheException(Exception):
	"""Parent for all exceptions raised by the cache."""
	pass

class CacheMissingException(CacheException):
	"""Raised when the asked value is unknown."""
	pass

class CacheExpiredException(CacheException):
	"""Raised when the asked value is outdated."""
	pass


# vim: ts=4:sw=4:ai
