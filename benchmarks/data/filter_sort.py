people = [("Alice", 22), ("Bob", 17), ("Carol", 31), ("Dave", 16), ("Eve", 25)]
adults = sorted([p for p in people if p[1] >= 18], key=lambda p: p[1])
print("[" + ", ".join(f"{name}({age})" for name, age in adults) + "]")
