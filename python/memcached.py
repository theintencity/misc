#!/usr/bin/env python
'''
A subset of memcache server.

---------------------
How to run the server?
---------------------

Run using Python 2.7.
For example, on Unix, Linux or OS X:

$ python memcached.py

On windows, use the right binary:

$ python27.exe memcache.py

See all command line options:

$ python memcached.py -h

Usage: memcached.py [options]

Options:
  -h, --help            show this help message and exit
  -p PORT, --port=PORT  listening port, default is widely used 11211
  -v, --verbose         enable debug level logging; default is info level
  --limit=LIMIT         size limit of the cache data in bytes; default is 0 to
                        disable limit

----------------------
Analysis
----------------------
"Tell us about what you expect the performance of your implementation to be,
and where you anticipate bottlenecks. Also tell us about where concurrency
issues like race conditions/deadlocks may arise (or how you've protected
against those issues).
Suggest ways in which the performance, reliability, or other limitations of
your implementation could be improved upon in the future."

The performance is poor because of these reasons. Suggestions to improve
are also listed.

1) CPython's Global Interpreter Lock (GIL) limits only one thread in
active python statement. For I/O bound this is fine, but for storing
and reading data from memory, this prevents advantage of multi-core hardware.
Other python interpreters could be used that do not have GIL.

2) Using one thread per socket is fine for small number of sockets, with
many requests on the same socket, i.e., small number of clients. Otherwise
it is better to use light-weight tasks, e.g., using Python gevent module,
or asyncore, to avoid the costly thread creation process.

3) Multi-threading in Python is poor, with no real performance benefit on
multi-core hardware for non I/O bound process.
Change to multi-processing. But that will require different synchronization
for the hash table data - use shared memory or other IPC mechanism (e.g.,
Unix socket).

4) The biggest bottleneck is due to the global lock on the full hash table.
This should be split into smaller parts of the table, and lock applied to
those smaller parts, e.g., have hash table of hash tables, and use a hash
on the key to determine which hash table to use, and have a lock on the
second level hash table. Something like:
  set(key, value) =>
    table = tables[H(key)]
    table.lock()
    table.set(key, value)
    table.unlock()

5) Python doesn't have built-in read-write lock. Using a read-write lock
(or RWLock) will help in the case of large number of reads and small number
of writes to the server.

6) A number of string operations are done, which are fine for smaller data.
But for frequent large data, it may be better to use buffers, and pointers
in the received packet. Since individual value in memcache is limited to only 1MB
this won't have significant impact. On the other hand, for larger data limit,
string operations and copying could be reduced when using pointers.

7) The buffered file wrapper API on top of socket used in the code also causes
unnecessary string copy. This could be replaced with low level socket APIs
with direct write, instead of file-style buffer (equivalent of fwrite vs write in C).

8) System APIs should be used to determine current memory pressure, and adjust
the request trottling or do cache cleanup. Otherwise, server will become too
slow if not enough memory. If no other significant processes are running, then
the command line --limit option can be used to supply the upper limit. But
currently this only counts the value sizes, and does not count accessories like
keys or flags or dict maintenance size.
'''

import logging, SocketServer, struct, traceback, collections, threading


class Message(object):
    '''A single request or response message.'''
    
    def __init__(self):
        self.magic = self.opcode = self.keylen = self.extralen = self.datatype = self.status = self.bodylen = 0
        self.opaque = self.cas = self.extra = self.key = self.value = ''
    
    @staticmethod
    def readfrom(rfile):
        '''Read a message from the socket (file-like) and return a message object.'''
        
        m = Message()
        
        header = rfile.read(24)
        if not header: return # connection was closed, return None
        
        logging.debug('recv [%d] %r', len(header), header)
        if len(header) < 24: raise RuntimeError('incorrect header')
        m.magic, m.opcode, m.keylen, m.extralen, m.datatype, m.status, m.bodylen, m.opaque, m.cas \
            = struct.unpack('!BBHBBHI4s8s', header)

        if m.magic != 0x80 and m.magic != 0x81: raise RuntimeError('incorrect packet')
            
        if m.extralen:
            m.extra = rfile.read(m.extralen)
            if len(m.extra) < m.extralen: raise RuntimeError('incorrect extralen')
        
        if m.keylen: # TODO: is there a limit to keylen?
            m.key = rfile.read(m.keylen)
            if len(m.key) < m.keylen: raise RuntimeError('incorrect keylen')
        
        if m.bodylen > m.extralen + m.keylen:
            # Send response with value too large (>1MB), and drop connection in set later.
            # TODO: for very very large (>10MB) just drop the connection.
            if m.bodylen - m.extralen - m.keylen > 10**7: raise RuntimeError('value too large')
            m.value = rfile.read(m.bodylen - m.extralen - m.keylen)
            if len(m.value) < m.bodylen - m.extralen - m.keylen: raise RuntimeError('incorrect bodylen')
        
        logging.debug('recv message %r', m)
        return m
        
    def writeto(self, wfile):
        '''Write this message to the socket (file-like).'''
        
        logging.debug('write message %r', self)
        wfile.write(struct.pack('!BBHBBHI4s8s', self.magic, self.opcode, self.keylen, self.extralen, \
                    self.datatype, self.status, self.bodylen, self.opaque, self.cas)
                    + self.extra + self.key)
        wfile.write(self.value) # separate out the value write, to avoid string concatenation (for if value is large)
    
    def __repr__(self):
        return 'message(magic=0x%02x, opcode=0x%02x, keylen=%r, extralen=%r, datatype=%r, status=0x%02x, bodylen=%r, extra=%r, key=%r)'%(
            self.magic, self.opcode, self.keylen, self.extralen, self.datatype, self.status, self.bodylen, self.extra, self.key)
    
    

class RequestHandler(SocketServer.StreamRequestHandler):
    '''Handle one client connection, read request and send response in a loop until disconnected, or error.'''
    
    def handle(self):
        logging.debug('received connection %r', self.request.getpeername())
        
        try:
            while True:
                request = Message.readfrom(self.rfile)
                if not request: break  # client disconnected
                
                # this is only a server
                if request.magic != 0x80: raise RuntimeError('received a response')
    
                response = Message()
                if request.opcode == 0x00: # Get
                    self.do_get(request, response)
                elif request.opcode == 0x01: # Set
                    self.do_set(request, response)
                else:
                    response.status, response.value = 0x81, "unknown command, only get and set allowed"
                
                response.magic, response.opcode, response.opaque = 0x81, request.opcode, request.opaque
                response.extralen, response.keylen = len(response.extra), len(response.key)
                response.bodylen = response.extralen + response.keylen + len(response.value)
                
                if response.status:
                    logging.debug('error response status=0x%02x value=%r', response.status, response.value)
                    
                response.writeto(self.wfile)
        except:
            # TODO: print exception only if log is enabled.
            traceback.print_exc()
        # will be disconnected, if not already
    
    def do_get(self, request, response):
        '''Process a "Get" request, and populate the response.'''
        
        if request.extra or request.value or not request.key: # mandatory conditions
            response.status, response.value = 0x04, "invalid arguments"
        else:
            try:
                flags, response.value = self.server.data[request.key]
                response.extra = struct.pack('!I', flags)
                response.status = 0
            except KeyError: # the key was not found in our data
                response.status, response.value = 0x01, "key not found"
    
    def do_set(self, request, response):
        '''Process a "Set" request, and populate the response.'''
        
        if not request.extra or not request.key or not request.value: # mandatory conditions
            response.status, response.value = 0x04, "invalid arguments"
        else:
            if request.cas:
                logging.debug('ignoring cas attribute in request')
                
            if len(request.value) > 1000000:
                response.status, response.value = 0x03, "value too large"
            else:
                flags, expire = struct.unpack('!II', request.extra)
                try:
                    self.server.data[request.key] = (flags, request.value)
                except MemoryError: # this may be explicit (see later) or implicit (by system)
                    response.status, response.value = 0x82, "out of memory"
    
        

def serve_forever(host, port, data):
    '''Create a one-thread-per-client TCP server to handle the requests.'''
    class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
        allow_reuse_address = True

    logging.debug('starting server on port %r', port)
    server = ThreadedTCPServer((host, port), RequestHandler)
    server.daemon_threads = True
    server.data = data
    server.serve_forever()



class HashTable(collections.OrderedDict):
    '''The data storage is a hash table (dict) with ordering, so that oldest items can be
    removed to make space for new items, and with lock, to support concurrency.'''

    def __init__(self, limit=None):
        collections.OrderedDict.__init__(self)
        self.limit, self.size = limit, 0
        self.lock = threading.RLock()
        logging.debug('created table with limit=%r', limit)
        
    def __setitem__(self, key, val):
        self.lock.acquire()
        try:
            # if the key exists, remove it to adjut size, before setting the new value.
            if key in self:
                flags, value = collections.OrderedDict.__getitem__(self, key)
                logging.debug('setitem key exists for %r, size=%r', key, len(value))
                self.size -= len(value)
                collections.OrderedDict.__delitem__(self, key)
                
            size = len(val[1])
            logging.debug('setitem size=%r+%r, limit=%r', self.size, size, self.limit)
            
            if self.limit is not None:
                # if limit is defined, make sure enough space is available, by
                # removing oldest items.
                while size + self.size > self.limit and self.size > 0:
                    ignore, value = collections.OrderedDict.popitem(self)
                    value = value[1]
                    logging.debug('removed oldest item of size %r, new size %r', len(value), self.size-len(value))
                    self.size -= len(value)
                    
                # if still not enough space, then throw an error.
                if size + self.size > self.limit:
                    logging.debug('reached size limit %r+%r > %r', self.size, size, self.limit)
                    raise MemoryError
            
            # finally update the dict
            self.size += size
            collections.OrderedDict.__setitem__(self, key, val)
        finally:
            self.lock.release()
        
    def __getitem__(self, key):
        self.lock.acquire()
        try:
            result = collections.OrderedDict.__getitem__(self, key)
            return result
        finally:
            self.lock.release()
        
    def __repr__(self):
        return 'HashTable(len=%r,limit=%r,size=%r)'%(len(self), self.limit, self.size)
    
    

if __name__ == '__main__':
    # command line options
    from optparse import OptionParser
    parser = OptionParser(usage="usage: %prog [options]")
    parser.add_option("-p", "--port", dest="port", type="int", default="11211",
                      help="listening port, default is widely used 11211")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                      help="enable debug level logging; default is info level")
    parser.add_option("--limit", dest="limit", type="int", default=0,
                      help="size limit of the cache data in bytes; default is 0 to disable limit")
    options, args = parser.parse_args()
    
    logging.basicConfig(level=logging.DEBUG if options.verbose else logging.INFO)
    
    try:
        serve_forever(host='', port=options.port, data=HashTable(limit=options.limit or None))
    except KeyboardInterrupt:
        pass
