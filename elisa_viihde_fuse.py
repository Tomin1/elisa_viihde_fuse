#!/usr/bin/env python3
# 
# Elisa Viihde File System in Userspace (FUSE)
# Copyright (c) 2016, Tomi Leppänen
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from collections import deque, namedtuple
from datetime import datetime, timedelta
from elisaviihde import elisaviihde
from fuse import FUSE, FuseOSError, Operations, LoggingMixIn
from time import strptime, strftime
from urllib.request import urlopen, Request
import errno, logging, os, re, stat

# Tell requests to shut up
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

TIME_FORMATTED = r'(?P<time>\d{2}\.\d{2}\.\d{4} \d{2}\.\d{2})'
TIME_ISO = r'(?P<time>\d{4}-\d{2}-\d{2} \d{2}\:\d{2})'
FILENAME_FORMATTED = r'(?P<name>.*) ' + TIME_FORMATTED + r'\.mpg'
FILENAME_ISO = r'(?P<name>.*) ' + TIME_ISO + '\.mpg'

TIME_FORMATTED_RE = re.compile(TIME_FORMATTED)
TIME_ISO_RE = re.compile(TIME_ISO)
FILENAME_FORMATTED_RE = re.compile(FILENAME_FORMATTED)
FILENAME_ISO_RE = re.compile(FILENAME_ISO)

TIME_FORMAT = '%d.%m.%Y %H.%M'
TIME_ISO_FORMAT = '%Y-%m-%d %H:%M'

CACHE_INVALIDATE_TIME = timedelta(0, 3600)

class EError(Exception):
    pass

DirCache = namedtuple('DirCache', ['folders', 'recordings'])
StreamUriCache = namedtuple('StreamUriCache', ['uri', 'time'])

class ElisaviihdeFUSE(LoggingMixIn, Operations):
    FOLDER = 0
    PROGRAM = 1


    def __init__(self, username, password, formatted_time=False):
        self.elisaviihde = elisaviihde()
        self.formatted_time = formatted_time
        self._dir_cache = {}
        self._stream_uri_cache = {}
        try:
            self.elisaviihde.login(username, password)
        except Exception:
            raise EError("Invalid credientials")

    def _get_folder_id(self, path, dir_id=None):
        if path in ('/', ''):
            return 0
        path, name = path.rsplit('/', 1)
        if dir_id is None:
            dir_id = self._get_folder_id(path)
        try:
            listing = self.elisaviihde.getfolders(dir_id)
        except Exception:
            raise FuseOSError(errno.EIO)
        for folder in listing:
            if folder['name'] == name:
                return folder['id']
        else:
            raise FuseOSError(errno.ENOENT)

    def _get_program_info(self, path, dir_id=None):
        if dir_id is None:
            parent_path, name = path.rsplit('/', 1)
            dir_id = self._get_folder_id(parent_path)
        else:
            name = path.rsplit("/", 1)[1]
        name = self._parse_filename(name)
        if name is None:
            raise FuseOSError(errno.ENOENT)
        if dir_id not in self._dir_cache:
            try:
                listing = self.elisaviihde.getrecordings(dir_id)
            except Exception:
                raise FuseOSError(errno.EIO)
        else:
            listing = self._dir_cache[dir_id].recordings
        for recording in listing:
            if recording['name'] == name.group('name'):
                if self.formatted_time:
                    if recording['startTime'] == name.group('time'):
                        return recording
                else:
                    startTime = self._get_iso_time(recording['startTime'])
                    if startTime == name.group('time'):
                        return recording
        else:
            raise FuseOSError(errno.ENOENT)

    def _get_program_id(self, path, dir_id=None):
        return self._get_program_info(path, dir_id)['programId']

    def _get_type(self, path):
        if path.endswith('.mpg'):
            return self.PROGRAM
        else:
            return self.FOLDER

    def _stat_program(self, path, dir_id=None):
        info = self._get_program_info(path, dir_id)
        time = info['startTimeUTC'] / 1000
        uri = self.elisaviihde.getstreamuri(info['programId'])
        request = Request(uri, method='HEAD')
        with urlopen(request) as response:
            size = int(response.getheader('Content-Length', 4096))
        return {
            'st_mode' : 0o444 | stat.S_IFREG,
            'st_nlink' : 1,
            'st_uid' : os.getuid(),
            'st_gid' : os.getgid(),
            'st_size' : size,
            'st_blksize' : 128*1024,
            'st_atime' : time,
            'st_mtime' : time,
            'st_ctime' : time,
        }

    def _stat_folder(self, path, dir_id=None): # FIXME: Missing stuff!
        if dir_id is None:
            dir_id = self._get_folder_id(path)
        return {
            'st_mode' : 0o555 | stat.S_IFDIR,
            'st_nlink' : 1,
            'st_uid' : os.getuid(),
            'st_gid' : os.getgid(),
            'st_size' : 4096,
            'st_atime' : 0,
            'st_mtime' : 0,
            'st_ctime' : 0,
        }

    def _create_filename(self, program):
        if self.formatted_time:
            startTime = program['startTime']
        else:
            startTime = self._get_iso_time(program['startTime'])
        return '{} {}.mpg'.format(program['name'], startTime)

    def _parse_filename(self, name):
        if self.formatted_time:
            return FILENAME_FORMATTED_RE.match(name)
        return FILENAME_ISO_RE.match(name)

    def _get_iso_time(self, time):
        return strftime(TIME_ISO_FORMAT, strptime(time, TIME_FORMAT))

    def getattr(self, path, fh=None):
        type_ = self._get_type(path)
        if type_ == self.FOLDER:
            return self._stat_folder(path)
        else:
            return self._stat_program(path)

    def open(self, path, flags):
        return self._get_program_id(path)

    def opendir(self, path):
        dir_id = self._get_folder_id(path)
        try:
            folders = self.elisaviihde.getfolders(dir_id)
            recordings = self.elisaviihde.getrecordings(dir_id)
        except Exception:
            raise FuseOSError(errno.EIO)
        self._dir_cache[dir_id] = DirCache(folders, recordings)
        return self._get_folder_id(path)

    def read(self, path, size, offset, fh):
        if (fh in self._stream_uri_cache and
                datetime.now() - self._stream_uri_cache[fh].time <
                CACHE_INVALIDATE_TIME):
            uri = self._stream_uri_cache[fh].uri
            self._stream_uri_cache[fh] = StreamUriCache(uri, datetime.now())
        else:
            try:
                uri = self.elisaviihde.getstreamuri(fh)
            except Exception:
                raise FuseOSError(errno.EACCES)
        request = Request(uri, headers={
            'Range': 'bytes={}-{}'.format(offset, offset+size)
        })
        with urlopen(request) as response:
            if response.getcode() / 100 == 4 or response.getcode() / 100 == 5:
                raise FuseOSError(errno.EIO)
            return response.read(size)

    def readdir(self, path, fh): # FIXME: Add attrs and stuff!
        if fh not in self._dir_cache:
            raise FuseOSError(errno.EIO) # FIXME: Check errno
        listing = ['.', '..']
        for folder in self._dir_cache[fh].folders:
            listing.append(folder['name'])
        for recording in self._dir_cache[fh].recordings:
            listing.append(self._create_filename(recording))
        return listing

    def releasedir(self, path, fh):
        if fh not in self._dir_cache:
            return 0
        del self._dir_cache[fh]
        return 0

    def destroy(self, path):
        self.elisaviihde.close()
        self.elisaviihde = None
        return 0

    def __call__(self, op, path, *args):
        if op in ('read', 'readdir'):
            self.log.debug('-> %s %s %s', op, path, repr(args))
            try:
                data = getattr(self, op)(path, *args)
                self.log.debug('<- %s len %s', op, len(data))
                return data
            except OSError as e:
                self.log.debug('<- %s %s', op, repr(str(e)))
                raise
            except Exception:
                self.log.debug('<- %s [Unhandled Exception]', op)
                raise
        else:
            return super().__call__(op, path, *args)

if __name__ == "__main__":
    import sys, argparse
    parser = argparse.ArgumentParser(
            description="Elisa Viihde File System in Userspace (FUSE)")
    parser.add_argument('mountpoint', help="mountpoint")
    parser.add_argument('username', help="your Elisa Viihde username")
    parser.add_argument('password', help="your Elisa Viihde password")
    parser.add_argument('-t', '--format-time', action='store_true',
            default=False, help="use Finnish time formatting in filenames")
    parser.add_argument('-n', '--no-fork', action='store_true', default=False,
            help="don't fork, leave running on foreground")
    parser.add_argument('-f', '--fork', action='store_false', dest='no_fork',
            help="fork even if --no-fork is set")
    parser.add_argument('-d', '--debug', action='store_true', default=False,
            help="set debugging on, requires --no-fork")
    args = parser.parse_args()

    if args.debug:
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        logger.addHandler(logging.StreamHandler())
        logger.debug("Set logging to DEBUG level")
    try:
        ev = ElisaviihdeFUSE(args.username, args.password, args.format_time)
    except EError as err:
        print(err, file=sys.stderr)
        sys.exit(32) # see mount(8)
    if args.no_fork:
        print("Not forking, press Ctrl+c to quit!")
        fuse = FUSE(ev, args.mountpoint, foreground=True)
    else:
        fuse = FUSE(ev, args.mountpoint)
    sys.exit(0)
