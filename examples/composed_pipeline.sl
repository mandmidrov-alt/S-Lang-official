sequence values from 1 for 8 steps using value * 2
filtered = values where item >= 8
squared = filtered map item * item
total = squared reduce 0 with acc + item
best = choose candidate from squared maximizing item
show values, filtered, squared, total, best
