# cli.py - command line interface
#
# Copyright (C) 2007-2009 Jesus M. Rodriguez
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import sys
import os
import commands

class CLI:
    def __init__(self):
        self.cli_commands = {}
        self._add_command(commands.ListCommand())

    def _add_command(self, cmd):
        self.cli_commands[cmd.get_name()] = cmd
        
    def _usage(self):
        print("Usage: %s MODULENAME --help" % (os.path.basename(sys.argv[0])))
        print("Supported modules:")
        print("loop through the commands and print usage")

    def main(self):
        if len(sys.argv) < 2 or not self.cli_commands.has_key(sys.argv[1]):
            self._usage()
            sys.exit(1)

        cmd = self.cli_commands[sys.argv[1]]
        cmd.main()


