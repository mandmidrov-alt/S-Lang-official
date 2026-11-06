from dataclasses import dataclass
@dataclass
class Planet:
    mass:float
    position:float
    velocity:float
    @property
    def speed(self): return self.velocity
earth=Planet(5.972e24,1.496e11,29780)
print(earth.mass,earth.position,earth.speed)
