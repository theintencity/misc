//
//  fakefs.h
//
//  class definitions.
//

#ifndef FakeFileSystem_fakefs_h
#define FakeFileSystem_fakefs_h

#include <iostream>
#include <string>
#include <sstream>
#include <list>
#include <memory>


namespace fakefs {

    class directory; // forward decl
    
    
    //
    // node class is abstract
    //
    
    class node {
    protected:
        size_t size;
        std::string name;
        
        bool added; // useful to avoid double add of a node in file system.
        
        node(const std::string& name);
        
        friend std::ostream & operator<<(std::ostream &o, const node& n);
        friend class directory; // so that "added" attribute can be accessed there
        
    public:
        virtual ~node() = 0; // make this an abstract class
        const std::string& get_name() const;
        void set_name(const std::string& value);
    };
    
    
    //
    // file node with buffer
    //
    
    class file: public node {
    private:
        // todo: use stringstream or stringbuf for efficiency.
        std::string buffer;
    
    public:
        file(const std::string& name);
        virtual ~file();
        size_t get_size() const;
        void append(const std::string& data);
        // todo: to reduce multiple copy, return unique_ptr to string.
        std::string read(size_t count, size_t offset=0) const;
    };
    
    
    // used in recuse method
    
    typedef void (*callback_t)(const node& node, void *opaque, size_t level);

    //
    // directory node with list of children nodes
    //
    class directory: public node {
    private:
        std::list<std::shared_ptr<node>> files;
        std::list<std::shared_ptr<node>>::iterator recent; // to speed up first/next iteration

        // invokes the callback on each node in DFS. Opaque is passed to callback.
        // level is increased for each level in the substree.
        void recurse(callback_t callback, void *opaque = NULL, size_t level=0) const;

        // make this private to avoid adding link within a directory.
        void add(std::shared_ptr<node> file);
        
    public:
        directory(const std::string& name);
        virtual ~directory();
        
        // ability to add a directory or file within this directory.
        void add(std::shared_ptr<file> file);
        void add(std::shared_ptr<directory> dir);
        
        std::shared_ptr<node> first();
        std::shared_ptr<node> next(const std::shared_ptr<const node>& current);
        void print_subtree(std::ostream& o);
    };
    
    //
    // link node points to some other node.
    //
    // use weak_ptr like a soft-link in real filesystem.
    //
    
    class link: public node {
    private:
        std::weak_ptr<node> pointer;
    public:
        link(const std::string& name, std::shared_ptr<node> pointer);
        ~link();
        std::shared_ptr<node> get_pointer() const;
    };
    

    //
    // global functions
    //
    
    std::shared_ptr<directory> create_root();
    
    
    //
    // inline methods that are trivial and one liner for readability of .cpp.
    // move these to .cpp file if this header file is included in many files, to reduce
    // generated code size.
    //
    
    //
    // node methods
    //
    
    inline
    node::node(const std::string& name):size(0),name(name),added(false) { }
    
    inline
    node::~node() { }
    
    inline const std::string&
    node::get_name() const { return name; }
    
    inline void
    node::set_name(const std::string& value) { this->name = value; }
    
    //
    // file methods
    //
    
    inline
    file::file(const std::string& name):node(name) { }
    
    inline
    file::~file() { }

    inline size_t
    file::get_size() const { return size; }

    inline void
    file::append(const std::string& data) { size += data.size(); buffer += data; }
    
    inline std::string
    file::read(size_t count, size_t offset) const { return buffer.substr(offset, count); }
    
    //
    // directory methods
    //
    
    inline
    directory::directory(const std::string& name):node(name) { recent = files.begin(); }
    
    inline
    directory::~directory() { }

    inline void
    directory::add(std::shared_ptr<file> item) {  add(std::dynamic_pointer_cast<node>(item));}
    
    inline void
    directory::add(std::shared_ptr<directory> item) {  add(std::dynamic_pointer_cast<node>(item));}
    
    //
    // link methods
    //
    
    inline
    link::link(const std::string& name, std::shared_ptr<node> pointer):node(name),pointer(pointer) { }
    
    inline
    link::~link() { }
    
    inline std::shared_ptr<node>
    link::get_pointer() const { return pointer.lock(); }
    
    
    //
    // global functions
    //
    
    inline std::shared_ptr<directory>
    create_root() { return std::shared_ptr<directory>(new directory("")); }

    
    inline std::ostream&
    operator<<(std::ostream &o, const node& p) { return o << p.name; }

    
}

#endif
