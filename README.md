Elisa Viihde Filesystem in Userspace
====================================

This is [my](https://github.com/Tomin1/) attempt to make [Elisa
Viihde](https://elisaviihde.fi/) [FUSE](https://github.com/libfuse/libfuse). It
might never be finished because of missing parts in Elisa Viihde API that would
be needed to make it useful. Even if this won't be useful, it will be a nice
experiment and I'll learn to use FUSE.

This uses elisaviihde.py from [enyone/elisaviihde branch
pre-1.5](https://github.com/enyone/elisaviihde/tree/pre-1.5). Download it and
put that somewhere in your python path.

This also needs [fusepy](https://github.com/terencehonles/fusepy/), which can
be installed with pip. Remember to use pip3 because I don't support python2.

Goals
-----
Main goals:
- Allow listing recordings
- Allow opening and reading the files to watch videos and copy them to local
  drives
- Resrict other users from touching the files if wanted (mount time option)

Other niche features:
- Moving files between directories
- Allow deleting recordings, user should be able to disable this

Problems
--------
Elisa Viihde API is not very friendly for this kind of operation. Maybe the
greatest problem of all is that it doesn't expose file sizes but only recording
lengths. That can't be used for file size (it might be possible to use that for
estimating file size). Instead I must make a HEAD request for every getattr
request for files.

Currently downloading files (only older recordings work) takes a lot of
requests and it is very slow. Even listing files is quite slow and takes many
seconds even for a small-ish directory.

Another problem is that some things require a lot of requests especially
if caching is not implemented.

A minor problem with the API is that there are no timestamps for folders and
currently I'm just ignoring them and using zero. That is probably the bast way
to handle that at the moment.

Disclaimer
----------
This program or it's developer(s) are not affiliated with Elisa or Elisa Viihde
in any way. You should not contact Elisa about problems in this application.

Elisa Viihde is a trademark of Elisa Oyj.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
