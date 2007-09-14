import os, stat, errno, time

class Config:
    def __init__(self, global_conf, local_conf): 
        self._config = {}

        # read global config
        self._readfile(global_conf)

        # read local overrides
        homedir = os.environ.get('HOME')
        if homedir is not None:
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
                line = f.readline()
                if len(line) == 0:
                    break
                pairs = line.strip().split('=')
                self._config[pairs[0]] = pairs[1]
        else:
            print "can't find " + str(config)
