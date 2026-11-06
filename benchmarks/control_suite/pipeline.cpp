#include <algorithm>
#include <iostream>
#include <vector>
struct S { int age, score; };
int main() {
    std::vector<S> v{{22,91},{17,88},{31,95},{16,72},{25,90}};
    v.erase(std::remove_if(v.begin(), v.end(), [](auto x){ return x.age < 18; }), v.end());
    std::sort(v.begin(), v.end(), [](auto a, auto b){ return a.score > b.score; });
    long total = 0;
    for (auto x : v) total += x.score * 2;
    std::cout << total << '\n';
}
