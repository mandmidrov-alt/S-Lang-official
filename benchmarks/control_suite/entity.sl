entity Planet:
    mass: kg
    position: m
    velocity: mps

property Planet.speed -> mps:
    return self.velocity

let earth = Planet(5.972e24 kg, 1.496e11 m, 29780 mps)
show earth.mass, earth.position, earth.speed
