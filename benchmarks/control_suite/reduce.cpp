#include <iostream>
int main() {
    long acc = 1;
    for (int value : {1,2,3,4,5}) acc *= value;
    std::cout << acc << '\n';
}
