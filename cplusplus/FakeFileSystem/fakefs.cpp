//
//  fakefs.cpp
//
//  Implementations of non-trivial methods.
//

#include <algorithm>
#include <cassert>
#include <stdexcept>

#include "fakefs.h"

using namespace fakefs;


//
// directory methods
//


// handle the case when directory is empty, and also update cached iterator.

std::shared_ptr<node>
directory::first() {
    if (!files.empty()) {
        recent = files.begin();
        return files.front();
    }
    return std::shared_ptr<node>(nullptr);
}


// avoid douple adding the node using the "added" flag

void
directory::add(std::shared_ptr<node> item) {
    if (item->added) {
        throw std::invalid_argument("item already has a parent");
    }
    
    item->added = true;
    recent = files.begin(); // reset cached iterator
    files.push_back(item);
}


// if cached iterator points to the current node, use the cached iterator to get the next node.
// otherwise linear search to find the right node to return. update the cached iterator too.

std::shared_ptr<node>
directory::next(const std::shared_ptr<const node>& current) {
    std::list<std::shared_ptr<node>>::iterator it;
    if (*recent == current) {
        it = recent;
    } else {
        it = find(files.begin(), files.end(), current);
    }
    if (it != files.end() && (++it) != files.end()) {
        recent = it;
        return *it;
    }
    recent = files.begin();
    return std::shared_ptr<node>(nullptr);
}


// recurse this subtree, calling the callback for every node in DFS.
// opaque is passed to the callback. level is incremented at each level
// in the hierarchy.

void
directory::recurse(callback_t callback, void *opaque, size_t level) const {
    callback(*this, opaque, level);
    
    for (std::list<std::shared_ptr<node>>::const_iterator it = files.begin();
         it != files.end(); ++it) {
        std::shared_ptr<node> file = *it;
        std::shared_ptr<directory> dir = std::dynamic_pointer_cast<directory>(file);
        if (dir) {
            dir->recurse(callback, opaque, level+1);
        } else {
            callback(*file, opaque, level+1);
        }
    }
}

//
// global functions
//

// print a single node name at the right indentation using level.
// used by print_subtree only.

static void
print_node(const node& file, void* opaque, size_t level) {
    std::ostream* o = (std::ostream*)(opaque);
    std::string indent(level, ' ');
    (*o) << indent << "/" << file << std::endl;
}


// recurse a subtree and print all nodes. uses print_node and directory::recurse.

void
directory::print_subtree(std::ostream& o) {
    recurse(print_node, &o);
}
