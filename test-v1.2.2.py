#!/usr/bin/python
#
# v1.2.2 XMLRPC test for smugmug.login.withPassword

import sys
import httplib
import xmlrpclib

API_KEY="4XHW8Aw7BQqbkGszuFciGZH4hMynnOxJ"

if len(sys.argv) < 3:
    print("test-v1.2.2.py <username> <password>")
    sys.exit(1)

verbose=True

# v1.2.1 works:
client1 = xmlrpclib.ServerProxy("https://api.smugmug.com/services/api/xmlrpc/1.2.1/", verbose=verbose)
session = client1.smugmug.login.withPassword(sys.argv[1], sys.argv[2], API_KEY)

# v1.2.2 does not work:
#client = xmlrpclib.ServerProxy("https://api.smugmug.com/services/api/xmlrpc/1.2.2/", verbose=verbose)
client2 = xmlrpclib.ServerProxy("https://secure.smugmug.com/services/api/xmlrpc/1.2.2/", verbose=verbose)

print str(client2)

session = client2.smugmug.login.withPassword(API_KEY, sys.argv[1], sys.argv[2])

print session

#eof
