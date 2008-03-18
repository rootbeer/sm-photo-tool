#!/usr/bin/env python

# smugmug - update and create smugmug galleries from the command line
# Use smugmug --help for more info
# 
# Copyright (C) 2004 John C. Ruttenberg
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# A copy of the GNU General Public License should be included at the bottom of
# this program text; if not, write to the Free Software Foundation, Inc., 59
# Temple Place, Suite 330, Boston, MA 02111-1307 USA

from sys import version_info, stderr, exit
if not (version_info[0] >= 2 and version_info[1] >= 3):
  stderr.write("Requires python 2.3 or more recent.  You have python %d.%d.\n"
               % (version_info[0], version_info[1]))
  stderr.write("Consider upgrading.  See http://www.python.org\n")
  exit(1)

from optparse import OptionParser, OptionGroup
import string
import re
from xmlrpclib import *
import httplib, mimetypes
import os
from os import path

version = "1.11"
key = "4XHW8Aw7BQqbkGszuFciGZH4hMynnOxJ"

# Changes:
#   1.11 bug: 1819595 - fix session bug. Add spaces after all commas.
#        change url for XMLRPC api.
#   1.10 Small bug fix for Windows (open file with "rb" mode)
#   1.9 Handle corrupt data files, add forced upload option.
#   1.8 Update .JPG and .GIF by default as well
#   1.7 Follow new API documentation.  Create properties work!  Send byte count
#       so incomplete uploads don't get processed.  XXX What about checksums?
#   1.6 Fix bug with listdir
#   1.5 Fix bug with --public and --no-public
#   1.4 Fix bug with boolean options and gallery creation
#   1.3 Document Title feature

def error(string):
  from sys import exit, stderr
  stderr.write(string + "\n")
  exit(1)

def message(opts, string):
  from sys import stderr
  if not opts.quiet:
    stderr.write(string)

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
    self.smdir = path.join(dir, "SMUGMUG_INFO")

  def exists(self):
    return path.isdir(self.smdir) and path.isfile(path.join(self.smdir, "gallery"))

  def create(self, gallery):
    if not path.isdir(self.smdir):
      os.mkdir(self.smdir)
    gallery_file = path.join(self.smdir, "gallery")
    if not path.isfile(gallery_file):
      filename_put_string(gallery_file, "%s\n" % gallery)
    self.created = True

  def gallery_id(self):
    if not self.exists():
      raise "No Localinformation for %s" % (dir)
    l = filename_get_line(path.join(self.smdir, "gallery"))
    return l

  def file_needs_upload(self, filename):
    try:
      if not self.exists():
        return False
      head, tail = path.split(filename)
      infofile = path.join(self.smdir, tail)
      if not path.isfile(infofile):
        return True
      #print "Checking %s... " % (infofile)
      l = filename_get_line(infofile)
      utime_s, size_s, count_s = string.split(l)
      if path.getmtime(filename) > int(utime_s):
        return True
      if os.stat(filename).st_size != int(size_s):
        return True
      return False
    except:
      return True

  def file_uploaded(self, filename):
    from time import time

    head, tail = path.split(filename)
    infofile = path.join(self.smdir, tail)

    if not path.isfile(infofile):
      count = 1
    else:
      l = filename_get_line(infofile)
      try:
        utime_s, size_s, count_s = string.split(l)
        count = int(count_s) + 1
      except:
        count = 1

    filename_put_string(infofile, "%d %d %d\n" % (time(),
                                                 os.stat(filename).st_size,
                                                 count))

  def file_upload_count(self, filename):
    head, tail = path.split(filename)
    infofile = path.join(self.smdir, tail)

    if not path.isfile(infofile):
      return 0
    else:
      l = filename_get_line(infofile)
      utime_s, size_s, count_s = string.split(l)
      return int(count_s)


def caption(filename, opts):
  head, ext = path.splitext(filename)
  capfile = head + ".caption"
  if path.isfile(capfile):
    result = filename_get_data(capfile)
    return f.read()
  if opts.filenames_default_captions:
    head, tail = path.split(head)
    return tail
  return None

def get_content_type(filename):
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

class Smugmug:
  def __init__(self, account, passwd):
    self.account = account
    self.password = passwd
    self.sp = ServerProxy("https://api.smugmug.com/services/api/xmlrpc/1.2.1/", verbose=True)
    self.categories = None
    self.subcategories = None
    self.login()

  def __del__(self):
    self.logout()

  def login(self):
    rc = self.sp.smugmug.login.withPassword(self.account, self.password, key)
    self.session = rc["Session"]["id"]

  def logout(self):
    self.sp.smugmug.logout(self.session)

  def create_album(self, name, opts):
    properties = {}
    if not opts.category or opts.category == '0':
      category = 0
    else:
      category = self.get_category(opts.category)
      if opts.subcategory:
        properties["SubCategoryID"] = self.get_subcategory(category,
                                                           opts.subcategory)
    if opts.description != None:
      properties["Description"] = opts.description
    if opts.keywords != None:
      properties["Keywords"] = opts.keywords
    if opts.gallery_password != None:
      properties["Password"] = opts.gallery_password
    if opts.public != None:
      properties["Public"] = opts.public
    if opts.show_filenames != None:
      properties["Filenames"] = opts.show_filenames
    if opts.comments_allowed != None:
      properties["Comments"] = opts.comments_allowed
    if opts.external_links_allowed != None:
      properties["External"] = opts.external_links_allowed
    if opts.show_camera_info != None:
      properties["EXIF"] = opts.show_camera_info
    if opts.easy_sharing_allowed != None:
      properties["Share"] = opts.easy_sharing_allowed
    if opts.print_ordering_allowed != None:
      properties["Printable"] = opts.print_ordering_allowed
    if opts.originals_allowed != None:
      properties["Originals"] = opts.originals_allowed
    if opts.community != None:
      properties["CommunityID"] = opts.community

    if opts.test:
      return 0
    else:
      return self.sp.smugmug.albums.create(self.session, name, category, properties)

  def get_categories(self):
    categories = self.sp.smugmug.categories.get(self.session)
    self.categories = {}
    for category in categories:
      self.categories[category['Title']] = category['id']

  def get_category(self, category_string):
    if re.match("\d+$", category_string):
      return string.atoi(category_string)
    if not self.categories:
      self.get_categories()

    if not self.categories.has_key(category_string):
      error("Unknown category " + category_string)
    else:
      return self.categories[category_string]

  def get_subcategory(self, category, subcategory_string):
    if re.match("\d+$", subcategory_string):
      return string.atoi(subcategory_string)
    if not self.subcategories:
      self.subcategories = {}
    if not self.subcategories.has_key(category):
      subcategories = self.sp.smugmug.subcategories.get(self.session, category)
      subcategory_map = {}
      for subcategory in subcategories:
        subcategory_map[subcategory['Title']] = subcategory['SubCategoryID']
      self.subcategories[category] = subcategory_map

    if not self.subcategories[category].has_key(subcategory_string):
      error("Unknown subcategory " + subcategory_string)
    else:
      return self.subcategories[category][subcategory_string]

  def upload_files(self, albumid, opts, args, local_information=None):
    from time import time
    from os import stat
    from string import atoi

    max_size = atoi(opts.max_size)

    total_size = 0
    sizes = {}
    files = []
    for file in args:
      if not path.isfile(file):
        message(opts, "%s not a file.  Not uploading\n")
        continue
      size = stat(file).st_size
      if size > max_size:
        message(opts, "%s size %d greater than %d.  Not uploading\n" %
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
      if not opts.test:
        self.upload_file(albumid, file, caption(file, opts))
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

  def upload_file(self, albumid, filename, caption=None):
    fields = []
    fields.append(['AlbumID', albumid])
    fields.append(['SessionID', self.session])
    if caption:
      fields.append(['Caption', caption])

    data = filename_get_data(filename)
    fields.append(['ByteCount', str(len(data))])

    file = ['Image', filename, data]
    self.post_multipart("upload.smugmug.com", "/photos/xmladd.mg", fields, [file])

  def post_multipart(self, host, selector, fields, files):
    """
    Post fields and files to an http host as multipart/form-data.  fields is a
    sequence of (name, value) elements for regular form fields.  files is a
    sequence of (name, filename, value) elements for data to be uploaded as
    files Return the server's response page.
    """
    content_type, body = self.encode_multipart_formdata(fields, files)
    h = httplib.HTTP(host)
    h.putrequest('POST', selector)
    h.putheader('content-type', content_type)
    h.putheader('content-length', str(len(body)))
    h.endheaders()
    h.send(body)
    errcode, errmsg, headers = h.getreply()
    #print errcode
    #print errmsg
    #print headers
    result = h.file.read()
    #print result
    h.close()
    return result

  def encode_multipart_formdata(self, fields, files):
    """
    fields is a sequence of (name, value) elements for regular form fields.
    files is a sequence of (name, filename, value) elements for data to be
    uploaded as files Return (content_type, body) ready for httplib.HTTP
    instance
    """
    #print fields
    BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
    CRLF = '\r\n'
    L = []
    for (key, value) in fields:
      L.append('--' + BOUNDARY)
      L.append('Content-Disposition: form-data; name="%s"' % key)
      L.append('')
      L.append(value)
    for (key, filename, value) in files:
      L.append('--' + BOUNDARY)
      L.append('Content-Disposition: form-data; name="%s"; filename="%s"'
               % (key, filename))
      L.append('Content-Type: %s' % get_content_type(filename))
      L.append("content-length: %d" % (len(value)))
      L.append('')
      L.append(value)
    L.append('--' + BOUNDARY + '--')
    L.append('')
    body = CRLF.join(L)
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    return content_type, body


def defaults_from_rc():
  from os import environ, path

  result = {}
  rcfile = path.join(environ['HOME'], '.smugmugrc')
  if not path.isfile(rcfile):
    return result
  f = file(rcfile, "rU")
  try:
    option = None
    for lwithnl in f:
      l = lwithnl[:-1]
      if l[-1] != "\\":
        has_continuation = False
      else:
        has_continuation = True
        l = l[:-1]
      if option:
        value += l
      else:
        colon_index = string.find(l, ":")
        if colon_index != -1:
          option = l[0:colon_index]
          value = l[colon_index+1:]
      if not has_continuation and option:
        result[string.strip(option)] = string.strip(value)
        option = None
  finally:
    f.close()
    return result

def to_bool(str):
  str = string.lower(str)
  if str == "true" or str == 'yes':
    return True
  elif str == 'false' or str == 'no':
    return False
  else:
    raise 'text bool conversation'


class Options:
  def __init__(self, argv):
    self.rcfile_options = defaults_from_rc()
    self.short_usage = \
      "sm-photo-tool create gallery_name [options] [file...]\n" \
      "       sm-photo-tool create_upload gallery_name [options] [file...]\n" \
      "       sm-photo-tool update [options]\n" \
      "       sm-photo-tool full_update [options]\n" \
      "       sm-photo-tool upload gallery_id [options] file...\n"
    self.parser = OptionParser(
      self.short_usage +
      "\n"
      "Create smugmug galleries and upload to them.  Mirror directory trees \n"
      "on smugmug and keep up to date.\n"
      "\n"
      "sm-photo-tool create gallery_name -- creates a new gallery and uploads the \n"
      "given files to it.\n"
      "\n"
      "sm-photo-tool create_upload gallery_name -- creates a new gallery and uploads the \n"
      "  given files to it, ignoring any previous upload state.  Use this if you\n"
      "  Want to do a 1-time upload to a new gallery without messing up future updates.\n"
      "\n"
      "sm-photo-tool update -- Updates the smugmug gallery associated with the \n"
      "working directory with any images that are either new or modified since\n"
      "creation or the last update\n"
      "\n"
      "sm-photo-tool full_update [options] -- Mirror an entire directory tree on \n"
      "smugmug.  The current working directory and all it's subdirectories are \n"
      "examined for image suitable image files.  Directories already \n"
      "corresponding to smugmug galleries, an update is performed.  Directories \n"
      "not already known to be created on smugmug, are created there and all \n"
      "the appropriate image files are uploaded.  The new gallery is named with \n"
      "the corresponding directory's relative path to the working directory where \n"
      "the command was invoked.  This can be overridden with a file named Title in the \n"
      "relevant directory.  If this exists, it's contents are used to name the new \n"
      "gallery.\n"
      "\n"
      "sm-photo-tool upload -- Simply upload the listed files to the smugmug \n"
      "gallery with the given gallery_id.  Unlike the above command, does not \n"
      "require or update any local information.\n"
      "\n\n"
      "sm-photo-tool accepts a number of command line options.  The default for \n"
      "any option can be specified in the a .smugmugrc file in the user's home \n"
      "directory.  The format of lines in that file is:\n"
      "  option_name: default\n"
      "For example:\n"
      "  login: joe@photographer.com\n"
      "  password: hotdog\n"
      "  public: True\n"
      "changes the default so that new galleries are public unless --no-public is \n"
      "given on the command line.  Notice that for boolean options, a default of \n"
      "True, yes, false, or no can be given  for the first given name of the \n"
      "option (the one without the ""no-"" prefix.).  Option values can cover \n"
      "more than one line.  \\ acts as a line continuation character."
      "\n\n"
      "Captions for specific images can be specified by files.  Suppose that \n"
      "xxxx.jpg is to be uploaded and that xxxx.caption exists in the same \n"
      "directory.  Then the contents of this file will be used to caption \n"
      "xxxx.jpg when it is uploaded")
      
    group = OptionGroup(self.parser,
                        "Common options",
                        "These apply to all functions")
    self.add_string_option(group, 'login', help="REQUIRED")
    self.add_string_option(group, "password", help="REQUIRED")
    self.add_bool_option(group, "quiet", help="Don't tell us what you are doing")
    self.add_bool_option(group, "test",
                         help="Don't actually create galleries or upload files.")
    self.parser.add_option_group(group)

    group = OptionGroup(self.parser,
                        "Create options",
                        "Only relevant when albums are created")
    self.add_string_option(group, "category")
    self.add_string_option(group, "subcategory")
    self.add_string_option(group, "description")
    self.add_string_option(group, "keywords")
    self.add_string_option(group, "gallery_password")
    self.add_bool_option(group, "public")
    self.add_bool_option(group, "show_filenames")
    self.add_bool_option(group, "comments_allowed", default=True)
    self.add_bool_option(group, "external_links_allowed", default=True)
    self.add_bool_option(group, "show_camera_info", default=True)
    self.add_bool_option(group, "easy_sharing_allowed", default=True)
    self.add_bool_option(group, "print_ordering_allowed", default=True)
    self.add_bool_option(group, "originals_allowed")
    self.add_string_option(group, "community")
    self.parser.add_option_group(group)

    group = OptionGroup(self.parser,
                        "Upload options",
                        "Only relevant when files are uploaded")
    self.add_bool_option(group, "filenames_default_captions")
    self.add_string_option(group, "max_size",
                           default="8000000",
                           help="Only upload if file <= this. By default "
                                "8000000 bytes.")
    self.add_string_option(group, "filter_regular_expression",
                           help="Only upload files that match. "
                                "By default, all .jpg and .gif files are "
                                "eligible.",
                           default=".*\\.(jpg|gif|JPG|GIF)")
    self.parser.add_option_group(group)

    self.options, self.args = self.parser.parse_args(argv)
    if not (self.options.login and self.options.password):
      error("No login and/or password.  Both are required")


  def help(self):
    error("Usage: " + self.short_usage +
          "\n       sm-photo-tool --help for complete documentaton\n")

  def add_bool_option(self, x, name, *args, **kwargs):
    try:
      kwargs['default'] = to_bool(self.rcfile_options[name])
    except:
      pass
    if not kwargs.has_key("default"):
      kwargs['default'] = False
    kwargs['help'] = "Default: %s" % (kwargs['default'])
    kwargs['action'] = 'store_true'
    x.add_option('--'+name, *args, **kwargs)
    kwargs['action'] = 'store_false'
    del kwargs['help']
    x.add_option('--no-'+name, *args, **kwargs)

  def add_string_option(self, x, name, *args, **kwargs):
    try:
      kwargs['default'] = self.rcfile_options[name]
    except:
      pass
    x.add_option('--'+name, *args, **kwargs)

def create(smugmug, name, dir, opts):
  album_id = smugmug.create_album(name, opts)
  li = LocalInformation(dir)
  li.create(album_id)

def update_dir(smugmug, dir, opts, files):
  li = LocalInformation(dir)
  
  files_to_upload = []
  for f in files:
    if re.match(opts.filter_regular_expression, f):
      file = path.join(dir, f)
      if li.file_needs_upload(file):
        files_to_upload.append(file)
  if len(files_to_upload) > 0:
    files_to_upload.sort()
    smugmug.upload_files(li.gallery_id(), opts, files_to_upload,
                         local_information=li)


def create_update(name, options):
  opts = options.options
  smugmug = Smugmug(opts.login, opts.password)
  create(smugmug, name, ".", opts)
  update_dir(smugmug, ".", opts, options.args)
  
def create_upload(name, options):
  opts = options.options
  rest = options.args
  smugmug = Smugmug(opts.login, opts.password)
  album_id = "%d" % smugmug.create_album(name, opts)
  smugmug.upload_files(album_id, opts, rest)

def upload(album_id, options):
  opts = options.options
  rest = options.args
  smugmug = Smugmug(opts.login, opts.password)
  smugmug.upload_files(album_id, opts, rest)

def update(options):
  opts = options.options
  smugmug = Smugmug(opts.login, opts.password)
  update_dir(smugmug, ".", opts, os.listdir("."))

def full_update(options):
  opts = options.options
  smugmug = Smugmug(opts.login, opts.password)
  opts = options.options
  for root, dirs, files in os.walk("."):
    try:
      dirs.remove("SMUGMUG_INFO")
    except:
      pass
    li = LocalInformation(root)
    # Look for at least one matching file before making directory
    for file in files:
      if re.match(opts.filter_regular_expression, file):
        if not li.exists():
          title_file = path.join(root, "Title")
          if path.isfile(title_file):
            name = filename_get_line(title_file)
          else:
            name = root[2:] # strip of initial ./ or .\
          create(smugmug, name, root, opts)
        update_dir(smugmug, root, opts, files)
        break

def main():
  from sys import argv, exit

  if len(argv) < 2:
    Options([]).help()
  elif argv[1] == 'create_upload':
    if len(argv) < 3:
      Options([]).help()
    create_upload(argv[2], Options(argv[3:]))
  elif argv[1] == 'create':
    if len(argv) < 3:
      Options([]).help()
    create_update(argv[2], Options(argv[3:]))
  elif argv[1] == 'upload':
    if len(argv) < 3:
      Options([]).help()
    upload(argv[2], Options(argv[3:]))
  elif argv[1] == 'update':
    update(Options(argv[2:]))
  elif argv[1] == 'full_update':
    full_update(Options(argv[2:]))
  elif argv[1] == '--help':
    Options(argv[1:])
  else:
    Options([]).help()

if __name__ == "__main__":
  main()
