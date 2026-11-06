#include <iostream>
#include <iomanip>
int main() {
    const double G = 6.67430e-11;
    const double mass = 1.989e30;
    double position = 1.496e11;
    double velocity = 29780.0;
    for (int i = 0; i < 1440; ++i) {
        double acceleration = G * mass / (position * position);
        velocity += acceleration * 60.0;
        position += velocity * 60.0;
    }
    std::cout << std::setprecision(17) << position << ' ' << velocity << '\n';
}
