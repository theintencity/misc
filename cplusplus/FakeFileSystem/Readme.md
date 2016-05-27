# FakeFileSystem

Design classes and write some simple methods for a simple mock file system.


## Assumptions and Limitations

Same name node could appear multiple times in a directory, unlike
a real file system. The size attribute is 0 for directory or link nodes, and number of
bytes for a file node. The name attribute is mandatory when constructing a node but
could be an empty string, and changeable later.
The name of the link node and its pointed to node are independent.

Only the required functions are implemented, without implementing
other natural functionality. For example, the requirement list mentions the ability
to add directory or file with a directory, but not a link, hence there is
no method to add a link within a
directory. The implementation is not thread-safe. String is used for I/O hence not
very efficient. The implementation uses C++11 smart pointers to reduce programming
error related to memory management.

Directory content is in a list, which makes it less efficient for the generic
next() node function. To speed up the common case of calling first() followed by
many next(), the last iterator is cached, so that a subsequent call to next()
from the previous item is O(1). Alternative could be to use map - which limits changes
to the file name, but makes next() more efficient - or to have a next pointer in node.

To avoid duplicate add of the same node, a flag is used in the node to determine
if the node object is already added or not.

For a richer implementation, a node or directory entry should maintain the
parent pointer, and implementation should be able to detect and avoid cycles when
adding link or directory within a directory. Or if it allows cycles, then detect
during recursive call to avoid cycle.

## Build and Test

The project was developed using Xcode, but I created a simple Makefile to compile a test
instead of checking in the Xcode projects. It compiles and runs on my OS X as well as 
Linux. 

To compile on OS X or Linux:
```
$ make
```

To test after compiling
```
$ make test
```

Due to C++11 features, it requires appropriate compiler version, e.g., gcc 4.7 or higher, I think.


On my OS X:
```
$ g++ -v
...
Apple LLVM version 6.0 (clang-600.0.56) (based on LLVM 3.5svn)
```

On my Linux:

```
g++ -v
...
gcc version 4.8.3 20140911 (Red Hat 4.8.3-9) (GCC) 
```

