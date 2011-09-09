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

import simplejson as json
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor, task, defer
from twisted.internet.defer import Deferred
import socket, zlib
import logs as log

from dnscache import DNSCache
from agent import Agent
import core


# Not in configuration file because need to be consistent over all nodes
USE_ZLIB=True

class UDPSender(DatagramProtocol):
	def __init__(self, onStart, getMsg, dest=None):
		self.d_onStart = onStart		# Deferred fired when protocol is up
		self.c_getMsg = getMsg		# Callback called every sendMessage()
		self.dest = dest

	def startProtocol(self):
		def setIp(result):
			self._ip=result
			self.d_onStart.callback(self) 

		# Set IP TOS field to Minimize-Delay
		self.transport.socket.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0x10)

		if self.dest is None:
			# Enable broadcast
			self.transport.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
			d=DNSCache.getInstance().get_bcast()
		else:
			d=DNSCache.getInstance().get_by_name(self.dest)
		
		d.addCallback(setIp)
		d.addErrback(log.err)

	def sendMessage(self):
		data=json.dumps(self.c_getMsg().value(), separators=(',',':'))

		if USE_ZLIB:
			crc=zlib.adler32(data)
			zip=zlib.compress(data)
			data=str(crc)+","+zip

		self.transport.write(data,(self._ip,core.cfg['UDP_PORT']))

class UDPListener(DatagramProtocol):
    def __init__(self, onReceive):
        self.c_onReceive = onReceive 

    def datagramReceived(self, data, (host, port)):
		try:
			if USE_ZLIB:
				(crc,zip)=data.split(',',1)
				data=zlib.decompress(zip)
				if int(crc) != zlib.adler32(data):
					raise Exception("Data from %s is corrupted." % (host))

			msg=json.loads(data)
		except Exception, e:
			log.warn("Error parsing message: %s" % (e))
		else:
			self.c_onReceive(msg,host)

class NetHeartbeat(object):

	MAX_RETRY = 2  # Maximum number of retry before panic mode

	def __init__(self, getMsg, dest = None):
		self.c_getMsg = getMsg
		self.dest = dest

	def start(self):
		self.retry=0
		d = Deferred()
		d.addCallback(self._run)
		self._port = reactor.listenUDP(0, UDPSender(d, self.c_getMsg, self.dest))

	def forcePulse(self):
		try:
			self._proto.sendMessage()
		except AttributeError:   # If _proto has not been started
			pass	
		except Exception, e:
			self._sendError(e)

	def _run(self, result):
		self._proto = result
		self._call = task.LoopingCall(self._proto.sendMessage)
		self._call.start(1).addErrback(self._sendError)

	def _sendError(self, reason):
		# Log all stacktrace to view the origin of this error
		log.err("Netheartbeat failure: %s" % (reason))
		if self.retry >= self.MAX_RETRY:
			log.emerg("Too many retry. Asking master to engage panic mode.")
			# Engage panic mode
			agent=Agent()
			d=agent.panic()
			d.addErrback(log.err)
			d.addBoth(lambda x: agent.disconnect())
		else:
			log.warn("Restarting network heartbeat within a few seconds...")
			self.retry+=1	# Will be resetted each elections (or panic recovery)
			reactor.callLater(2, self._run, self._proto)

	def stop(self):
		if self._call.running:
			self._call.stop()
			
		try:	
			return defer.maybeDeferred(self._port.stopListening)
		except AttributeError:
			# If self._port is not defined
			return defer.succeed(None)


# vim: ts=4:sw=4:ai
