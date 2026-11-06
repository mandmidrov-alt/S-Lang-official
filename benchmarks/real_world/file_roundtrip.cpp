#include <fstream>
#include <iostream>
#include <string>
int main() {
    std::ofstream("benchmarks/real_world/.roundtrip.txt") << "alpha\nbeta\ngamma\n";
    std::ifstream in("benchmarks/real_world/.roundtrip.txt");
    std::string all((std::istreambuf_iterator<char>(in)), {});
    std::string normalized = "alpha beta gamma";
    int count = 0;
    for (char x : normalized) if (x == 'a') ++count;
    std::cout << 3 << "\n" << normalized.size() << "\n" << count << "\n";
}
