import difflib

FILE1 = "inputs/1mb_file.txt"
NUM_OF_FILES = 3

with open(FILE1, 'r') as f1:
    for i in range(1,NUM_OF_FILES+1):
        with open(f"file_{i}.txt", 'r') as f2:
            diff = difflib.unified_diff(
                f1.readlines(),
                f2.readlines(),
                fromfile=FILE1,
                tofile=f"file_{i}.txt",
            )

            if list(diff):
                print(f"file_{i}.txt is different from {FILE1}")


