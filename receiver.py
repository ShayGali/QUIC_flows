from QUIC_api import *

HOST = '0.0.0.0'  # listen on all interfaces
PORT = 4269


async def receiver() -> None:
    conn = QUIC()
    conn.listen(HOST, PORT)

    # Keep receiving file data until the connection is closed
    while (file_data := await conn.receive()) is not None:
        # save the file data to a file
        for i, file in enumerate(file_data):
            with open(f"file_{i+1}.txt", "wb") as f:
                f.write(file)
    conn.close()


if __name__ == '__main__':
    asyncio.run(receiver())
