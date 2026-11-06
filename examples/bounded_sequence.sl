# Bounded semantic iteration: stop when the current value reaches the condition.
sequence values from 1 for up to 20 steps until value >= 100 using value * 3 + 1
total = values reduce 0 with acc + item
show values
show total
