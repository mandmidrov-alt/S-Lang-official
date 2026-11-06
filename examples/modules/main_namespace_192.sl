module demo
import "geometry.sl" as geo

let disk = geo.Circle(10 m)
let c = geo.circumference(10 m)
show disk.radius, disk.diameter
show c
