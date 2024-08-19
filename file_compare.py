import difflib

FILE1 = "big_file.txt"
for i in range(3):
    with open(FILE1, 'r') as f1, open(f"file_{i}.txt", 'r') as f2:
        diff = difflib.unified_diff(
            f1.readlines(),
            f2.readlines(),
            fromfile=FILE1,
            tofile=f"file_{i}.txt",
        )
        for line in diff:
            print(line)
