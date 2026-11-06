#include <algorithm>
#include <iostream>
#include <numeric>
#include <vector>
#include <string>
struct S{std::string n;int age,score;};
int main(){std::vector<S>a={{"Alice",22,91},{"Bob",17,88},{"Carol",31,95},{"Dave",16,72},{"Eve",25,90},{"Frank",20,84}};std::vector<S>e;for(auto&s:a)if(s.age>=18)e.push_back(s);std::sort(e.begin(),e.end(),[](auto&a,auto&b){return a.score>b.score;});std::vector<int>x;for(auto&s:e)x.push_back(s.score);int best=*std::max_element(x.begin(),x.end());double avg=std::accumulate(x.begin(),x.end(),0.0)/x.size();for(auto&s:e)std::cout<<s.n<<" ";std::cout<<"\n";for(auto v:x)std::cout<<v<<" ";std::cout<<"\n"<<best<<"\n"<<avg<<"\n";}
