G = 6.67430e-11
sun_mass = 1.989e30
position = 1.496e11
velocity = 29780.0
for _ in range(86400 // 60):
    acceleration = G * sun_mass / (position * position)
    velocity = velocity + acceleration * 60.0
    position = position + velocity * 60.0
print(position)
print(velocity)
