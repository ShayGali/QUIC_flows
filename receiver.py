from QUIC_api import *
import os
import random
import socket

HOST = '0.0.0.0'  # listen on all interfaces
PORT = 4269


def create_file(size: int, file_name: str):
    if os.path.isfile(file_name):
        if os.stat(file_name).st_size == size * 1024 * 1024:
            return
    with open(file_name, 'wb') as f:
        # for i in range(size * 1024 * 1024):
        f.write(random.randbytes(size * 1024 * 1024))
    #     f.write(b'/0' * size * 1024 * 1024)




def server(host: str, port: int) -> None:
    # Create a UDP socket
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        # Bind the socket to the address
        sock.bind((host, port))

        while True:
            # Receive data from the client
            data, addr = sock.recvfrom(1024)
            print(f"Received {data.decode()} from {addr}")

            # Send data to the client
            sock.sendto(data, addr)
    pass

if __name__ == "__main__":
    # server(host, port)
    create_file(3, "aviva.bin")