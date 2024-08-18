import asyncio

from QUIC_api import *

HOST = '127.0.0.1'
PORT = 4269


async def sender():
    #
    # with open("big_file.txt", "r") as f1, open("small_file.txt.txt", "w") as f2:
    #     file_data1 = f1.read()
    #     file_data2 = f2.read()
    #
    #     await conn.send_files([file_data1.encode(), file_data2.encode()])
    #     conn.close()
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
