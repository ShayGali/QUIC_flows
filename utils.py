import os
import random

def create_file(size: int, file_name: str):
    if os.path.isfile(file_name):
        if os.stat(file_name).st_size == size * 1024 * 1024:
            return
    with open(file_name, 'wb') as f:
        # for i in range(size * 1024 * 1024):
        f.write(random.randbytes(size * 1024 * 1024))
    #     f.write(b'/0' * size * 1024 * 1024)

