from QUIC_api import *

conn = QUIC()

conn.connect_to("192.168.0.1", 4269)

file_data = open("aviva.bin", "rb").read()

conn.send(file_data)
