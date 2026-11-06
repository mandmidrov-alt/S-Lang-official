G=6.67430e-11
m=1.989e30
x=1.496e11
v=29780.0
for _ in range(10_000_000):
    a=G*m/(x*x)
    v=v+a
    x=x+v
print(f'position = {x:.15g} m')
print(f'velocity = {v:.15g} mps')
