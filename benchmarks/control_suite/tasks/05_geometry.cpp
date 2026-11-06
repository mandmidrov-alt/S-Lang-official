#include <cmath>
#include <iomanip>
#include <iostream>
int main() {
    const double radius = 10.0;
    std::cout << std::setprecision(15);
    std::cout << "area = " << M_PI * radius * radius << " m2\n";
    std::cout << "circumference = " << 2 * M_PI * radius << " m\n";
}
