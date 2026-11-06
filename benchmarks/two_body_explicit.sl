entity Body:
    mass: kg
    position: m
    velocity: mps

let sun = Body(1.989e30 kg, 0 m, 0 mps)
let earth = Body(5.972e24 kg, 1.496e11 m, 29780 mps)

constant G = 6.67430e-11 m3_per_kg_s2

rule acceleration(body: Body, attractor: Body):
    G * attractor.mass / distance(body, attractor)^2

action advance(body: Body, attractor: Body, step: s):
    let a = acceleration(body, attractor)
    set body.velocity = body.velocity + a * step
    set body.position = body.position + body.velocity * step

simulate earth from 0 s to 86400 s step 60 s using advance(earth, sun)

show earth.position
show earth.velocity
