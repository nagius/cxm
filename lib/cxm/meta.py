# -*- coding:Utf-8 -*-

# cxm - Clustered Xen Management API and tools
# Copyleft 2010-2012 - Nicolas AGIUS <nicolas.agius@lps-it.fr>
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


""" program meta-information """

name = "cxm"
version = "0.9.4"
update_date = "February 2013"
license = "GPL"
authors = [("Nicolas Agius","nicolas.agius@lps-it.fr")]
url = "https://github.com/nagius/cxm"
description = "Clustered Xen Management API and tools"
manbook = description

long_description = """ """

classifiers = [
    "Environment :: Console",
    "Environment :: No Input/Output (Daemon)",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: GNU General Public License (GPL)",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python",
    "Topic :: System :: Operating System Kernels :: Linux",
    "Topic :: System :: Systems Administration",
]


def parser2pod(parser):
	"""Generate POD options list from an instance of OptionParser."""
	def get_pod_from_options(options):
		item="=over\n\n"
		for option in options:
			item += "=item "
			opts=list()
			opts.extend(option._short_opts)
			opts.extend(option._long_opts)
			item += ", ".join([ "B<"+opt+">" for opt in opts ])
			if option.metavar:
				item += " I<"+option.metavar+">"

			item += "\n\n"+option.help+"\n\n"

		item += "=back\n\n"
		return item

	pod=""
	pod += get_pod_from_options(parser.option_list)
	for group in parser.option_groups:
		pod += "B<"+group.title+">\n\n"
		pod += get_pod_from_options(group.option_list)
		
	return pod

# vim: ts=4:sw=4:ai
