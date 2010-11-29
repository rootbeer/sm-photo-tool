# sm_wrapper.py - Smugmug API wrapper
#
# Copyright (C) 2007-2009 Jesus M. Rodriguez
# Copyright (C) 2004 John C. Ruttenberg
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
import string
import re
import xmlrpclib
import xml.dom.minidom
import httplib
import cookielib
import Cookie
import hashlib
import os
from log import log
import getpass

# sm-photo-tool version:  (XXX unused?)
version = "1.16"
# sm_photo_tool offical key:
API_KEY = "4XHW8Aw7BQqbkGszuFciGZH4hMynnOxJ"

def error(string):
    sys.stderr.write(string + "\n")
    sys.exit(1)

def message(opts, string):
    from sys import stdout
    if opts:
        if not opts.quiet:
            stdout.write(string)
    else:
        stdout.write(string)
    stdout.flush()

def minutes_seconds(seconds):
    if seconds < 60:
        return "%d" % seconds
    else:
        return "%d:%02d" % (seconds / 60, seconds % 60)

def filename_get_line(name):
    f = file(name, "rU")
    l = f.readline()
    f.close()
    return l[:-1]

def filename_get_data(name):
    f = file(name, "rb")
    d = f.read()
    f.close()
    return d

def filename_put_string(filename, string):
    f = file(filename, "w")
    f.write(string)
    f.close()

class LocalInformation:
    def __init__(self, dir):
        self.dir = dir
        self.smdir = os.path.join(dir, "SMUGMUG_INFO")

    def exists(self):
        return os.path.isdir(self.smdir) and \
            os.path.isfile(os.path.join(self.smdir, "gallery"))

    def create(self, gallery):
        if not os.path.isdir(self.smdir):
            os.mkdir(self.smdir)
        gallery_file = os.path.join(self.smdir, "gallery")
        if not os.path.isfile(gallery_file):
            filename_put_string(gallery_file, "%s\n" % gallery)
        self.created = True

    def gallery_id(self):
        if not self.exists():
            raise "No LocalInformation for %s" % (dir)
        l = filename_get_line(os.path.join(self.smdir, "gallery"))
        return l

    def file_needs_upload(self, filename):
        try:
            if not self.exists():
                return False
            head, tail = os.path.split(filename)
            infofile = os.path.join(self.smdir, tail)
            if not os.path.isfile(infofile):
                return True
            l = filename_get_line(infofile)
            utime_s, size_s, count_s = string.split(l)
            if os.path.getmtime(filename) > int(utime_s):
                return True
            if os.stat(filename).st_size != int(size_s):
                return True
            return False
        except:
            return True

    def file_uploaded(self, filename):
        from time import time

        head, tail = os.path.split(filename)
        infofile = os.path.join(self.smdir, tail)

        if not os.path.isfile(infofile):
            count = 1
        else:
            l = filename_get_line(infofile)
            try:
                utime_s, size_s, count_s = string.split(l)
                count = int(count_s) + 1
            except:
                count = 1

        filename_put_string(infofile, "%d %d %d\n" % (time(),
            os.stat(filename).st_size, count))

    def file_upload_count(self, filename):
        head, tail = os.path.split(filename)
        infofile = os.path.join(self.smdir, tail)

        if not os.path.isfile(infofile):
            return 0
        else:
            l = filename_get_line(infofile)
            utime_s, size_s, count_s = string.split(l)
            return int(count_s)

#
# Get the caption for a given filename.  If a ".caption" file exists
# for the file to upload, use the contents of that file.  Otherwise,
# if the filenames-are-default-captions bool is set, use the name of the
# file as the caption.
#
# Alternatively, instead of doing captioning through this tool, once
# an image is uploaded to smugmug, the smugmug system will use the
# "IPTC:Caption-Abstract" EXIF header field as a default caption.
# (Try 'exiftool -Caption-Abstract="this is a test caption" foo.jpg'.)
#
def caption(filename, filenames_default_captions):
    head, ext = os.path.splitext(filename)
    capfile = head + ".caption"
    if os.path.isfile(capfile):
        result = filename_get_data(capfile)
        return result
    if filenames_default_captions:
        head, tail = os.path.split(head)
        return tail
    return None

def get_content_type(filename):
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

#
# Create a 'cookie-aware' transport for XMLRPC lib to use instead of
# its default 'SafeTransport'
#
class XmlRpcCookieTransport(xmlrpclib.SafeTransport):
    '''
    Adds to request all cookies from previous request
    '''

    user_agent = "sm-photo-tool/%s" % version

    def __init__(self):
        xmlrpclib.SafeTransport.__init__(self)
        self._cookies = {}

    def request(self,
                host,
                handler,
                request_body,
                verbose=False):
        """
        Replace xmlrcplib.Transport's 'request' method.  Re-implement
        it to cache SmugMug's special session Cookies.
        """

        # Connect (using SSL):
        h = self.make_connection(host)
        if verbose:
            h.set_debuglevel(1)

        try:
            # Compose the request
            self.send_request(h, handler, request_body)
            self.send_host(h, host)
            self.send_user_agent(h)

            # XXX factor out cookie-header-string
            # Add any cookies that have been cached
            cookieStrs=[]
            for c in self._cookies.keys():
                cstr = "%s=%s" % (c, self._cookies[c]) # XXX encode cookies?
                cookieStrs.append(cstr)
                
            if cookieStrs:
                # Append a single "Cookie" header will all of the cookies
                h.putheader("Cookie", ";".join(cookieStrs))

            self.send_content(h, request_body)

            # Get the reply
            errcode, errmsg, headers = h.getreply()

            # Any HTTP error causes us to just bail here
            if errcode != 200:
                raise ProtocolError(
                    host + handler,
                    errcode, errmsg,
                    headers 
                   )

            # XXX factor out header-scraping-cookie-updating
            # Save off any cookies received
            cookies = None
            if headers.has_key('set-cookie'):
                cookies = headers['set-cookie']

            if headers.has_key('set-cookie2'):
                raise RuntimeError, "Dunno what to do with v2 cookies ..."

            if cookies:
                #
                # XXX cookie mashing.  RFC2616 states that HTTP header
                # messages must not change semantics when concatenated
                # with a ','.  However, the 'expire' attribute
                # includes text like "expires=Tue, 28-Dec-2010
                # 06:46:11 GMT;" in the cookie value (note the comma).
                # So, we first replace the expire date commas with
                # '%2C', then split the string on commas!
                #
                # This wouldn't be an issue if the Python http libraries
                # just returned a list of Set-Cookie headers instead of a
                # single comma-joined string.
                #
                COMMA_STR = '%2C'
                assert not COMMA_STR in cookies # need a more unique string if so ...
                
                # Fix embedded commas
                (cookies, fixCt) = re.subn(r'expires=(...),',
                                           r'expires=\1' + COMMA_STR, cookies)
                
                for cstr in cookies.split(","):
                    cstr = cstr.lstrip().replace(COMMA_STR, ',')
                
                    if False:
                        c = Cookie.BaseCookie(cstr)
                        # NOTE: c.iterkeys() gives the (single) "key" of the cookie
                        # NOTE: c["key"].iterkeys() gives the attrs of the cookie
                        print "COOKIE", str(c)
                        for k in c.keys():
                            print "   C:", k  #, c[k]
                            for attr in c[k].keys():
                                print "      A:", attr, c[k][attr]
                                
                    cookie=cstr.split(';')[0] # strip all the 'flags'
                    (name, val) = cookie.split("=")

                    self._cookies[name] = val

            self.verbose = verbose
            return self.parse_response(h.getfile())

        except xmlrpclib.Fault:
            # Catch xmlrpclib.Fault here just so it doesn't get caught below
            raise
            
        except Exception:
            # All unexpected errors leave connection in
            # a strange state, so we clear it.
            h.close()
            raise
            

class SmugmugException(Exception):
    def __init__(self, value, code=0):
        self.code = code
        self.value = value

    def __str__(self):
        return repr(self.value)

class Smugmug:
    def __init__(self, account, passwd):
        self.categories = None
        self.subcategories = None
        self.session = None
        self.transport = XmlRpcCookieTransport()

        if not account:
            raise RuntimeError, "Must provide a valid login (via dot-file or --login option)"
        if not passwd:
            raise RuntimeError, "Must provide a valid password (via dot-file or --password option)"

        # XXX
        xmlrpcVerbose = True
        xmlrpcVerbose = False

        self.account = account
        if passwd is None:
            passwd = getpass.getpass()
        self.password = passwd

        # XXX v1.2.2 doesn't have 'login.withPassword' 
        self.sp = xmlrpclib.ServerProxy(
            "https://api.smugmug.com/services/api/xmlrpc/1.2.1/",
            #"https://secure.smugmug.com/services/api/xmlrpc/1.2.2/",
            transport=self.transport,
            verbose=xmlrpcVerbose)

        if False:
            # Use XMLRPC introspection to print all the methods ...
            print "METHODS:"
            for m in self.sp.system.listMethods():
                sig = self.sp.system.methodSignature(m)
                print m, str(sig)

        self.login()

    def __del__(self):
        self.logout()

    def login(self):
        try:
            # XXX 1.2.2 API:??
            #rc = self.sp.smugmug.login.withPassword(API_KEY, self.account, self.password)
            rc = self.sp.smugmug.login.withPassword(self.account, self.password, API_KEY)
            self.session = rc["Session"]["id"]
        except xmlrpclib.Fault, err:
            raise SmugmugException(err.faultString, err.faultCode)

        print "SESSION: ", str(self.session)
        log.debug("Logged in. Session: %s" % (str(self.session)))

    def logout(self):
        try:
            if self.session:
                self.sp.smugmug.logout(self.session)
        except xmlrpclib.Fault, err:
            # only raise the error if it is not an invalid session
            if not err.faultCode == 3: # 3 == invalid session
                raise SmugmugException(err.faultString, err.faultCode)

    def _set_property(self, props, name, opt):
        """
        Safely set a property, ignoring it if the value is None
        """
        if opt is not None:
            log.debug("Setting album property %s to %s" % (name, str(opt)))
            props[name] = opt
        else:
            log.debug("Not setting album property %s" % (name))


    def create_album(self, name, opts):
        props = {}

        if opts != None:
            #
            # Figure out the category and/or sub-category to create
            # the new album in
            #
            catID = 0
            subcatID = None

            if opts.categoryID:
                # --category-id is overriden by --category
                catID = int(opts.categoryID)
                
            if opts.category:
                catID = self.get_category(opts.category)

            if catID != 0:
                log.debug("Chose catID %u from (%s / %s)" % \
                          (catID, str(opts.categoryID), opts.category))

                # Only consider the subcategory options if a category
                # was set

                if opts.subcategoryID:
                    subcatID = int(opts.subcategoryID)

                if opts.subcategory:
                    subcatID = self.get_subcategory(catID, opts.subcategory)

                if subcatID is not None:
                    log.debug("Chose sub-catID %u from (%s / %s)" % \
                              (subcatID, str(opts.subcategoryID), opts.subcategory))

            self._set_property(props, "Description", opts.description)
            self._set_property(props, "Keywords", opts.keywords)
            self._set_property(props, "Password", opts.gallery_password)
            self._set_property(props, "Public", opts.public)
            self._set_property(props, "Filenames", opts.show_filenames)
            self._set_property(props, "Comments", opts.comments_allowed)
            self._set_property(props, "External", opts.external_links_allowed)
            self._set_property(props, "EXIF", opts.show_camera_info)
            self._set_property(props, "Share", opts.easy_sharing_allowed)
            self._set_property(props, "Printable", opts.print_ordering_allowed)
            self._set_property(props, "Originals", opts.originals_allowed)
            self._set_property(props, "CommunityID", opts.community)
            self._set_property(props, "WorldSearchable", opts.world_searchable)
            self._set_property(props, "SmugSearchable", opts.smug_searchable)
            self._set_property(props, "SquareThumbs", opts.square_thumbs)
            self._set_property(props, "HideOwner", opts.hide_owner)
            self._set_property(props, "SortMethod", opts.sort_method)
            self._set_property(props, "SubCategoryID", subcatID)

        rsp = self.sp.smugmug.albums.create(self.session, name, catID, props)
        return rsp['Album']['id']

    def get_categories(self):
        categories = self.sp.smugmug.categories.get(self.session)
        self.categories = {}
        for category in categories['Categories']:
            self.categories[category['Name']] = category['id']

    def get_category(self, category_string):
        """
        Return the category id for the given category string
        """

        if not self.categories:
            self.get_categories()

        if not self.categories.has_key(category_string):
            error("Unknown category " + category_string)
        else:
            return self.categories[category_string]

    def get_subcategory(self, category, subcategory_string):
        """
        Return the integer subcategory id number for the given
        subcategory name of the given category.
        """

        if not self.subcategories:
            self.subcategories = {}
        if not self.subcategories.has_key(category):
            subcategories = self.sp.smugmug.subcategories.get(
                self.session, category)
            subcategory_map = {}
            for subcategory in subcategories['SubCategories']:
                subcategory_map[subcategory['Name']] = subcategory['id']
            self.subcategories[category] = subcategory_map

        if not self.subcategories[category].has_key(subcategory_string):
            error("Unknown subcategory " + subcategory_string)
        else:
            return self.subcategories[category][subcategory_string]

    def upload_files(self, albumid, opts, args, local_information=None):
        from time import time
        from os import stat

        max_size = opts.max_size

        total_size = 0
        sizes = {}
        files = []
        for file in args:
            if not os.path.isfile(file):
                message(opts,"%s is not a file. Not uploading.\n" % file)
                continue
            size = stat(file).st_size
            if size > max_size:
                message(opts, "%s size %d greater than %d. Not uploading\n" %
                    (file, size, max_size))
            else:
                files.append(file)
                sizes[file] = size
                total_size += size

        t = time()
        total_xfered_bytes = 0

        for file in files:
            t0 = time()
            message(opts, file + "...")
            self.upload_file(albumid, file, caption(file, False))
            t1 = time()
            if local_information:
                local_information.file_uploaded(file)
            seconds = t1 - t0
            try:
                bytes_per_second = sizes[file] / seconds
                total_xfered_bytes += sizes[file]
                estimated_remaining_seconds = \
                    (total_size - total_xfered_bytes) / bytes_per_second
                message(opts, "[OK] %d bytes %d seconds %dKB/sec ETA %s\n" % (
                    sizes[file],
                    seconds,
                    bytes_per_second / 1000,
                    minutes_seconds(estimated_remaining_seconds)))
            except:
                pass

        total_seconds = time() - t
        try:
            message(opts, "%s %d bytes %dKB/sec\n" % (
                minutes_seconds(total_seconds),
                total_size,
                (total_size / total_seconds) / 1000))
        except:
            pass

    # List all the images in the given album
    def list_files(self, albumid, opts, args):
        # Get IDs in album
        resp = self.sp.smugmug.images.get(self.session, albumid)
        imageIDs = resp['Images']

        for imgHandle in imageIDs:
            imgID = imgHandle['id']
            imgKey = imgHandle['Key']
            resp = self.sp.smugmug.images.getInfo(self.session, imgID, imgKey)
            img = resp['Image']
            fn = '<unnamed>'
            if 'FileName' in img:
                fn = img['FileName']
            message(opts, "%d: %s (%d x %d):%s\n" %
                (imgID, fn, img['Width'], img['Height'],
                 img['Caption']))

    # List all the albums/galleries the current user has
    def list_galleries(self, opts, arg):
        # Get IDs in album
        resp = self.sp.smugmug.albums.get(self.session)
        albums = resp['Albums']

        albById={}
        for alb in albums:
            id = alb['id']
            albById[id] = alb

        for id in sorted(albById.keys()):
            alb = albById[id]
            message(opts, "%9d: %s\n" % (id, alb['Title']))

    def upload_file(self, albumid, filename, caption=None):
        data = filename_get_data(filename)

        # prep HTTP PUT to upload image
        h = httplib.HTTPConnection("upload.smugmug.com")
        h.connect()
        h.putrequest('PUT', "/" + filename)
        h.putheader('Content-Length', str(len(data)))
        h.putheader('Content-MD5', hashlib.md5(data).hexdigest())
        h.putheader('X-Smug-SessionID', self.session)
        h.putheader('X-Smug-Version', '1.2.1')
        h.putheader('X-Smug-ResponseType', 'Xml-RPC')
        h.putheader('X-Smug-AlbumID', str(albumid))
        h.putheader('X-Smug-FileName', filename)
        if caption:
            h.putheader('X-Smug-Caption', caption)
        h.endheaders()
        log.debug("PUT: header: %s" % str(h))

        h.send(data)

        # response output
        resp = h.getresponse()
        log.debug("%s: %s" % (resp.status, resp.reason))
        resultStr = resp.read()
        h.close()
        log.debug("PUT: result: %s" % resultStr)

        #Method response looks like this:
        # <methodResponse>
        # <fault>
        # <value>
        #  <struct>
        #   <member>
        #    <name>method</name>
        #    <value>
        #     <string>smugmug.images.upload</string>
        #    </value>
        #   </member>
        #   <member>
        #    <name>faultCode</name>
        #    <value>
        #     <int>5</int>
        #    </value>
        #   </member>
        #   <member>
        #    <name>faultString</name>
        #    <value>
        #     <string>system error (invalid album id)</string>
        #    </value>
        #   </member>
        #  </struct>
        # </value>
        # </fault>
        # </methodResponse> (__init__/1091)
        # 

        resultObj = xml.dom.minidom.parseString(resultStr)
        root = resultObj.documentElement
        if root.tagName == "methodResponse":
            print "Got a 'methodResponse'", str(root)

        faults = root.getElementsByTagName("fault")
        if faults:
            print "Has Fault?", faults

        resultObj.unlink()
