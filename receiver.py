from QUIC_api import *

HOST = '0.0.0.0'  # listen on all interfaces
PORT = 4269


async def receiver() -> None:
    conn = QUIC()
    conn.listen(HOST, PORT)

    # Keep receiving file data until the connection is closed
    while (file_data := await conn.receive()) is not None:
        print("Received file data:")
        # print(file_data)
        # save the file data to a file

    conn.close()


if __name__ == '__main__':
    asyncio.run(receiver())
