raw = "  S-Lang   makes   data   processing   concise.  "
clean = " ".join(raw.split())
lowered = clean.lower()
words = lowered.split(" ")
replaced = lowered.replace("concise", "clear")
print(len(words))
print(lowered.count("a"))
print(len(replaced))
