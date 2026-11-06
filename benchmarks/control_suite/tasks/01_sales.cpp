#include <algorithm>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>
struct Sale { std::string name; double price, quantity; int region; };
int main() {
    std::vector<Sale> sales={{"A",10,3,1},{"B",7,5,2},{"C",20,2,1},{"D",4,10,3},{"E",12,1,1}};
    std::vector<Sale> regional;
    for (auto s: sales) if (s.region==1) regional.push_back(s);
    std::sort(regional.begin(), regional.end(), [](auto&a,auto&b){return a.price>b.price;});
    std::vector<double> values; for(auto s:regional) values.push_back(s.price*s.quantity);
    double total=std::accumulate(values.begin(),values.end(),0.0);
    for(auto&s:regional) std::cout<<s.name<<" "; std::cout<<"\n";
    for(auto v:values) std::cout<<v<<" "; std::cout<<"\n"<<total<<"\n";
}
