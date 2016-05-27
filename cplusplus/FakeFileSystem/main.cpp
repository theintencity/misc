//
//  main.cpp
//
//  testing of various functions.
//

#include <iostream>
#include <cassert>
#include <stdexcept>
#include <cstring>
#include <cstddef>

#include "fakefs.h"

#ifdef NDEBUG  // force debugging
#undef NDEBUG
#endif

using namespace std;
using namespace fakefs;

int main(int argc, const char * argv[]) {
    
    // create tree
    
    cout << "running test" << endl;
    
    shared_ptr<directory> root = create_root();
    
    shared_ptr<file> file1(new file("file1"));
    root->add(file1);
    
    shared_ptr<file> file2(new file("file2"));
    root->add(file2);
    
    shared_ptr<directory> dir3(new directory("dir3"));
    root->add(dir3);
    
    shared_ptr<file> file31(new file("file31"));
    dir3->add(file31);
    
    shared_ptr<file> file32(new file("file32"));
    dir3->add(file32);
    
    shared_ptr<directory> dir33(new directory("dir33"));
    dir3->add(dir33);
    
    try {
        dir3->add(file2);
        assert(false); // failed to detect double add
    } catch (const invalid_argument& e) {
        // ignore
    }
    
    shared_ptr<file> file4(new file("file4"));
    root->add(file4);
    
    stringstream sout; // to verify
    root->print_subtree(sout); // replace sout with cout to print to stdout
    assert(sout.str() == std::string("/\n") +
           " /file1\n" +
           " /file2\n" +
           " /dir3\n" +
           "  /file31\n" +
           "  /file32\n" +
           "  /dir33\n" +
           " /file4\n");

    // create link
    
    shared_ptr<fakefs::link> link5(new fakefs::link("link5", dir3));
    shared_ptr<fakefs::link> link6(new fakefs::link("link6", file32));
    
    assert(link5->get_name() == "link5");
    assert(link5->get_pointer()->get_name() == "dir3");

    // get_size and read/append
    
    assert(file2->get_size() == 0);
    assert(file2->read(1) == "");
    
    // test with embedded nul
    
    std::string str1("hello \0there.", 13), str2("how are you?");
    
    assert(strlen(str1.c_str()) != str1.size());
    assert(strlen(str2.c_str()) == str2.size());
    
    file2->append(str1);
    assert(file2->get_size() == str1.size());
    file2->append(str2);
    assert(file2->get_size() == str1.size() + str2.size());
    
    std::string data1 = file2->read(str1.size());
    assert(data1 == str1);
    std::string data2 = file2->read(str2.size(), str1.size());
    assert(data2 == str2);
    
    // overflow offset or limit
    
    std::string data3 = file2->read(str2.size()+10, str1.size());
    assert(data3 == str2);
    std::string data4 = file2->read(10, str1.size() + str2.size());
    assert(data4 == "");
    
    // first and next
    
    std::shared_ptr<node> item = root->first();
    assert(item == file1);
    
    item = dir3->first();
    assert(item == file31);
    
    // for O(1) sequential step
    item = dir3->next(item);
    assert(item == file32);
    
    item = dir3->next(item);
    assert(item == dir33);
    
    item = dir3->next(item);
    assert(item == nullptr);
    
    // for O(n) search
    item = dir3->next(file32);
    assert(item == dir33);
    
    cout << "successfully completed" << endl;
    
    return 0;
}
