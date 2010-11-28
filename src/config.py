# config.py - access to the user's sm-photo-tool config file
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

import os, stat, errno, time

class Config:
    def __init__(self, global_conf, local_conf): 
        self._config = {}

        # read global config
        self._readfile(global_conf)

        # read local overrides
        homedir = os.environ.get('HOME')
        if homedir is not None and local_conf is not None:
            l_config = os.path.join(homedir, local_conf)
            self._readfile(l_config)

    def __setitem__(self, key, value):
        self._config[key] = value

    def __getitem__(self, key):
        return self._config[key]

    def __str__(self):
        return str(self._config)

    def _readfile(self, config):
        if os.path.isfile(config):
            f = open(config, "r")
            while f:
                rawline = f.readline()
                line = rawline.strip()
                if len(line) == 0:
                    break
                if line[0] == "#":
                    # ignore comment lines
                    continue
                pairs = line.split('=')
                self._config[pairs[0]] = pairs[1]

    def get_int(self, property, default=0):
        return int(self.get_property(property, default))

    def get_property(self, property, default=None):
        return self._config.get(property, default)

    def set_property(self, name, value):
        self.__setitem__(name, value)

    def get_as_dict(self):
        return self._config
