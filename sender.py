import asyncio

from QUIC_api import *

HOST = '127.0.0.1'
PORT = 4269


async def sender():
    with open("medium_file.txt", "r") as f, open("big_file.txt", "r") as f2:
        file_data = f.read().encode()
        file_data2 = f2.read().encode()

        conn = QUIC()

        conn.connect_to(HOST, PORT)
        # await conn.send_files([file_data, file_data, file_data2, file_data2, file_data, file_data2])
        await conn.send_files([file_data, file_data])
        # sleep for two seconds
        await asyncio.sleep(0.01)
        conn.close()


if __name__ == '__main__':
    asyncio.run(sender())
