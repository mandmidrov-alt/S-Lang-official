#include <iostream>
int main() {
    int v[] = {12, 18, 21, 27, 32, 40};
    int total = 0, high = 0, count = 0;
    for (int x : v) {
        total += x;
        if (x >= 25) { high += x; ++count; }
    }
    std::cout << total << "\n";
    std::cout << total / 6.0 << "\n";
    std::cout << high << "\n";
    std::cout << count << "\n";
}
