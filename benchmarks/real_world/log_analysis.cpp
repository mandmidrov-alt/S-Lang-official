#include <iostream>
#include <string>
int main() {
    std::string a = "error disk full";
    std::string b = "error timeout";
    std::cout << 2 << "\n" << (a + "|" + b).size() << "\n";
}
