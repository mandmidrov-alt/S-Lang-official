#include <algorithm>
#include <iostream>
#include <string>
#include <vector>
struct Person { std::string name; int age; };
int main() {
    std::vector<Person> people{{"Alice",22},{"Bob",17},{"Carol",31},{"Dave",16},{"Eve",25}};
    std::vector<Person> adults;
    for (const auto& p : people) if (p.age >= 18) adults.push_back(p);
    std::sort(adults.begin(), adults.end(), [](const auto& a, const auto& b){ return a.age < b.age; });
    std::cout << "[";
    for (size_t i=0;i<adults.size();++i) { if(i) std::cout << ", "; std::cout << adults[i].name << "(" << adults[i].age << ")"; }
    std::cout << "]\n";
}
