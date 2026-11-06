#include <iostream>
#include <iomanip>
int main() {
    const double G=6.67430e-11, mass=1.989e30, dt=60.0;
    double position=1.496e11, velocity=29780.0;
    for(int i=0;i<1440;++i){ double a=G*mass/(position*position); velocity += a*dt; position += velocity*dt; }
    std::cout << std::setprecision(15) << position << "\n" << velocity << "\n";
}
