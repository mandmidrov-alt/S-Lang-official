G=6.67430e-11
mass=1.989e30
position=1.496e11
velocity=29780
for _ in range(1440):
    a=G*mass/(position*position)
    velocity += a*60
    position += velocity*60
print(position,velocity)
