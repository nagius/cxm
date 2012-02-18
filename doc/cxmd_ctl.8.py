#!/usr/bin/env python
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

import os.path, subprocess, sys
sys.path += ["lib", "../lib"]
from cxm import meta, clid

name="cxmd_ctl"
mansect="8"

input = """
=head1 NAME

""" + name + """ - Clustered Xen Management's daemon controller tool


=head1 VERSION

This is the manual page of """+name+" version "+meta.version+"""


=head1 SYNOPSIS

"""+name+""" options


=head1 OPTIONS

"""

# Generate options list from parser
input += meta.parser2pod(clid.get_parser())
	
input += """


=head1 DESCRIPTION

The B<"""+name+"""> command line tool is used to control cxm's daemon.
See L<cxmd(8)> for more informations.


=head1 CONFIGURATION

This program use F</etc/xen/cxm.conf> as configuration file.
See L<cxm.conf(5)> for more informations.


=head1 SEE ALSO

L<cxm(1)> L<cxm.conf(5)> L<cxmd(8)> 


=head1 AUTHORS

"""

# Generate authors list
for author, email in meta.authors:
	input += author +" <"+email+">\n"


# convert the Pod to nroff
pod2man = subprocess.Popen([
    "/usr/bin/pod2man",
    "--name", name,
    "--section", mansect,
    "--center", meta.manbook,
    "--release", meta.name+" v"+meta.version,
#    "--stderr",
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
)
(output, errors) = pod2man.communicate(input)

if errors:
    sys.stderr.write("errors while generating man page: "+errors)

path = name+"."+mansect
if os.path.isdir("doc"): path = "doc/"+path
open(path, "w").write(output)

# vim: ts=4:sw=4:ai
