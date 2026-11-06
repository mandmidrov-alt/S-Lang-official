#include <iostream>
#include <sstream>
#include <string>
int main() {
    std::string clean="S-Lang makes data processing concise.";
    std::string lower="s-lang makes data processing concise.";
    std::string replaced="s-lang makes data processing clear.";
    std::stringstream ss(lower); int words=0; std::string w; while(ss>>w) ++words;
    int count=0; for(char c: lower) if(c=='a') ++count;
    std::cout << words << "\n" << count << "\n" << replaced.size() << "\n";
}
