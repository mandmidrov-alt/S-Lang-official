module geometry
export Circle, circumference

entity Circle:
    radius: m

function circumference(radius: m) -> m:
    return radius * 2

property Circle.diameter -> m:
    return self.radius * 2
