#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
struct Row { std::string role; int age, score; };
int main(){std::ifstream in("benchmarks/scale/people_50000.csv"); std::string line; std::getline(in,line); Row r; long long total=0; while(std::getline(in,line)){std::stringstream ss(line); std::string x; std::getline(ss,x,','); std::getline(ss,x,','); r.age=std::stoi(x); std::getline(ss,x,','); r.score=std::stoi(x); std::getline(ss,r.role,','); if(r.age>=18 && r.role=="engineer") total+=r.score;} std::cout<<total<<"\n";}
