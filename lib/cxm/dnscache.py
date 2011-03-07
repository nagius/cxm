# -*- coding:Utf-8 -*-

# cxm - Clustered Xen Management API and tools
# Copyleft 2011 - Nicolas AGIUS <nagius@astek.fr>
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


import socket, struct, fcntl


class DNSCache(object):

	# This is old-school Singleton pattern, Python's way really sucks !
	__instance = None

	@staticmethod
	def getInstance():
		if not DNSCache.__instance:
			 DNSCache.__instance=DNSCache()
		return DNSCache.__instance
			
	# Singleton pattern: Should be private, but with Python all is public
	def __init__(self):
		self.ifname="eth0"
		self._resolve = dict()  # IP -> hostname
		self._reverse = dict()	# hostname -> IP
		self.bcast = None

		self.name=socket.getfqdn()
		self.ip=socket.gethostbyname(self.name)
		self._resolve[self.ip]=self.name
		self._reverse[self.name]=self.ip

	def add(self, name): # TODO async
		ip=socket.gethostbyname(name)
		self._resolve[ip]=name
		self._reverse[name]=ip	

	def delete(self, name):
		try:
			del self._resolve[self._reverse[name]]
			del self._reverse[name]
		except KeyError:
			pass
		
	def clear(self):
		self._resolve.clear()
		self._reverse.clear()
		self.__init__()

	def get_by_ip(self, ip): # TODO async
		try:
			return self._resolve[ip]
		except KeyError, e:
			name=socket.gethostbyaddr(ip)[0]
			self._resolve[ip]=name
			self._reverse[name]=ip	
			return name

	def get_by_name(self, name): # TODO async
		try:
			return self._reverse[name]
		except KeyError, e:
			ip=socket.gethostbyname(name)
			self._resolve[ip]=name
			self._reverse[name]=ip	
			return ip

	def get_bcast(self):
		if self.bcast is None:
			try:
				s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				self.bcast=socket.inet_ntoa(fcntl.ioctl(
					s.fileno(),
					0x8919,  # SIOCGIFBRDADDR 
					struct.pack('256s', self.ifname[:15])
					)[20:24])
			except IOError:
				self.bcast="255.255.255.255"
		
		return self.bcast



# vim: ts=4:sw=4:ai
