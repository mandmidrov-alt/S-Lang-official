#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
struct Row { std::string name, role; int age, score; };
int main() {
    std::ifstream in("benchmarks/real_world/data/people.csv");
    std::string line; std::getline(in, line); std::vector<Row> rows;
    while (std::getline(in, line)) { std::stringstream ss(line); std::string x; std::vector<std::string> v; while (std::getline(ss,x,',')) { if (!x.empty() && x.back() == '\r') x.pop_back(); v.push_back(x); } rows.push_back({v[0],v[3],std::stoi(v[1]),std::stoi(v[2])}); }
    int total=0, count=0; for (auto &r: rows) if (r.age>=18 && r.role=="engineer") { total += r.score; ++count; }
    std::cout << total << "\n" << count << "\n";
}
