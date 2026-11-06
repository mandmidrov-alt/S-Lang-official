#include <algorithm>
#include <iostream>
#include <numeric>
#include <vector>
int main(){std::vector<double>v={2.5*100,12*20,80*4,5*50};std::cout<<v[0]<<" "<<v[1]<<" "<<v[2]<<" "<<v[3]<<"\n"<<std::accumulate(v.begin(),v.end(),0.0)<<"\n"<<*std::min_element(v.begin(),v.end())<<"\n"<<*std::max_element(v.begin(),v.end())<<"\n";}
