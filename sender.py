import asyncio

from QUIC_api import *

HOST = '127.0.0.1'
PORT = 4269


async def sender():
    with open("big_file.txt", "r") as f:
        file_data = f.read()

        conn = QUIC()

        conn.connect_to(HOST, PORT)
        await conn.send_files([file_data.encode()]*3)
        # sleep for two seconds
        await asyncio.sleep(0.01)
        conn.close()


if __name__ == '__main__':
    asyncio.run(sender())
