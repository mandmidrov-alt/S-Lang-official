#include <iostream>
struct Planet {
    double mass, position, velocity;
    double speed() const { return velocity; }
};
int main() {
    Planet earth{5.972e24, 1.496e11, 29780};
    std::cout << earth.mass << ' ' << earth.position << ' ' << earth.speed() << '\n';
}
