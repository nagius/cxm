#!/usr/bin/env python
# cxm - Clustered Xen Management API and tools
# Copyleft 2010 - Nicolas AGIUS <nagius@astek.fr>
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
from cxm import meta, cli

name="cxm"
mansect="1"

input = """
=head1 NAME

""" + name + """ - Clustered Xen Management tool


=head1 VERSION

This is the manual page of """+name+" version "+meta.version+"""


=head1 SYNOPSIS

"""+name+""" F<subcommand> [args] [options]


=head1 OPTIONS

=over

"""

# Generate options list from parser
input += meta.parser2pod(cli.get_parser())
	
input += """

=back


=head1 DESCRIPTION

The B<"""+name+"""> command line tool is used to manage Xen guest domains, aka. virtuals machines, on a cluster of Xen nodes.
This program can be used to create, shutdown, or migrate domains. It can also be used to list current domains, and do cluster maintenance.

As we are on a cluster, these commands can be run from any node of the cluster, and mostly do operations on all nodes.

The basic structure of every """+name+""" command is similar to L<xm(1)>.


=head1 SUBCOMMANDS

The following subcommands manipulate domains or whole cluster.  Most commands take domain-fqdn as the first parameter.

=over

"""

# Generate subcommands' help from cli's help
for subcommand in cli.SUBCOMMAND_HELP.keys():
	args=cli.SUBCOMMAND_HELP[subcommand][0]
	input += "=item " + subcommand + " " + args.replace('<','F<') + "\n\n"
	input += "\n".join(cli.SUBCOMMAND_HELP[subcommand][1::]) +"\n\n"
	
input += """

=back


=head1 CONFIGURATION

This program use F</etc/xen/cxm.conf> as configuration file.
See L<cxm.conf(5)> for more informations.


=head1 SEE ALSO

L<xm(1)> L<cxm.conf(5)> L<cxmd(8)> L<cxmd_ctl(8)>


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
