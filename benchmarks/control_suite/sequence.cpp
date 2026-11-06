#include <iostream>
int main() {
    long value = 1;
    long total = 0;
    for (int i = 0; i < 12; ++i) {
        total += value;
        value = value * 3 + 1;
    }
    std::cout << total << '\n';
}
