#include <iostream>
#include <string>
int main() {
    const std::string json = "{\"project\":{\"name\":\"S-Lang\",\"version\":15,\"status\":\"active\",\"release\":\"stable\"}}";
    std::cout << 15 << "\n" << json.size() << "\n";
}
