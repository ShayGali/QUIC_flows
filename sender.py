import asyncio

from QUIC_api import *

HOST = '127.0.0.1'
PORT = 4269

NUM_OF_FILES = 10
FILE_NAME = "1mb_file.txt"


async def sender(file_name: str, num_of_files: int):
    with open(FILE_NAME, "rb") as f:
        file_data = f.read()

        conn = QUIC()

        conn.connect_to(HOST, PORT)
        await conn.send_files([file_data] * NUM_OF_FILES)
        # sleep for two seconds
        await asyncio.sleep(0.001)
        conn.close()


if __name__ == '__main__':
    # get arguments from the command line
    import sys

    if len(sys.argv) > 2:
        FILE_NAME = sys.argv[1]
        NUM_OF_FILES = int(sys.argv[2])

    if len(sys.argv) > 1:
        NUM_OF_FILES = int(sys.argv[1])

    asyncio.run(sender(FILE_NAME, NUM_OF_FILES))
