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


from pprint import pprint

import simplejson as json
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor, task, defer
from twisted.internet.defer import Deferred
import time, socket
import logs as log

from dnscache import DNSCache



# TODO: gérer corruption messages

CLUSTER_NAME="cltest" # TODO a passer en fichier
PORT=6666

class UDPSender(DatagramProtocol):
	def __init__(self, onStart, getMsg, dest=None):
		self.d_onStart = onStart		# Deferred fired when protocol is up
		self.c_getMsg = getMsg		# Callback called every sendMessage()
		self.dest = dest

	def startProtocol(self):
		def setIp(result):
			self._ip=result
			self.d_onStart.callback(self) 

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

		self.transport.write(data,(self._ip,PORT))
		#       raise error.MessageLengthError("test")

class UDPListener(DatagramProtocol):
    def __init__(self, onReceive):
        self.c_onReceive = onReceive 

    def datagramReceived(self, data, (host, port)):
		try:
			msg=json.loads(data)
		except Exception, e:
			log.err("Error parsing message : %s" % (e))
		else:
			self.c_onReceive(msg,host)

class NetHeartbeat(object):
	def __init__(self, getMsg, dest = None):
		self.c_getMsg = getMsg
		self.dest = dest

	def start(self):
		d = Deferred()
		d.addCallback(self._run)
		self._port = reactor.listenUDP(0, UDPSender(d, self.c_getMsg, self.dest))

	def _run(self, result):
		self._proto = result
		self._call = task.LoopingCall(self._proto.sendMessage)
		self._call.start(1).addErrback(self._sendError)

	def _sendError(self, reason):
		# TODO a gérer mieux que ca
		log.err("Socket write error: %s" % (reason))

	def stop(self):
		self._call.stop()
		return defer.maybeDeferred(self._port.stopListening)


# vim: ts=4:sw=4:ai
