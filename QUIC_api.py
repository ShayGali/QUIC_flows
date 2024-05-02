import asyncio
from dataclasses import dataclass, field
from typing import Dict, List
from enum import Enum
import socket
import pickle
import random

FRAME_SIZE = 1024


class QUIC:

    def __init__(self):
        # Create a UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Set the maximum packet size to a random value between 1000 and 2000
        self.max_packet_size = int(random.uniform(1000, 2000))

        # for later use
        self.host = None
        self.port = None

        self.stream_id_generator = 0
        self.streams: Dict[int, bytes] = {}

    def listen(self, host: str, port: int):
        """
        This function will listen for incoming connection.
        :param host: The IP address to listen on.
        :param port: The port to listen on.
        :return:
        """
        self.host = host
        self.port = port

        # Bind the socket to the address
        self.socket.bind((self.host, self.port))

        # Wait for the client to send a SYN packet
        data, addr = self.socket.recvfrom(self.max_packet_size)
        packet = pickle.loads(data)  # Deserialize the data

        # check if the client sent a SYN packet
        if packet.header.flags.syn:
            # Send an ACCEPT_CONNECTION packet to the client
            packet.header.flags = PacketType.ACCEPT_CONNECTION.value
            self.socket.sendto(pickle.dumps(packet), addr)
        else:  # If the client did not send a SYN packet
            raise ConnectionError("The client did not send a SYN packet")

    def connect_to(self, host: str, port: int):

        self.host = host
        self.port = port

        # Send a SYN packet to the receiver so start the connection
        packet = QUICPacket(PacketType.SYN)
        self.socket.sendto(pickle.dumps(packet), (self.host, self.port))

        # Wait for the receiver to accept the connection
        data, addr = self.socket.recvfrom(self.max_packet_size)
        packet = pickle.loads(data)
        if packet.header.flags.syn and packet.header.flags.ack:
            print(f"Connection established with {addr} {packet.header.connection_id}")
        else:
            raise ConnectionError("The receiver did not accept the connection")


    async def send(self, data: bytes):
        stream_id = self.stream_id_generator
        self.stream_id_generator += 1
        number_of_packets = len(data) // self.max_packet_size
        last_packet_size = len(data) % self.max_packet_size

        # send the all packets except the last one
        for i in range(number_of_packets):
            packet = QUICPacket(PacketType.DATA)
            offset = i * self.max_packet_size
            data_to_send = data[offset: (i + 1) * self.max_packet_size]
            packet.add_frame(QUICPacket.Frame(stream_id, offset, self.max_packet_size, data_to_send))
            self.socket.sendto(pickle.dumps(packet), (self.host, self.port))
            # TODO: wait for the receiver to acknowledge the packet

        # send the last packet
        packet = QUICPacket(PacketType.DATA)
        offset = number_of_packets * self.max_packet_size
        data_to_send = data[offset: offset + last_packet_size]
        packet.add_frame(QUICPacket.Frame(stream_id, offset, last_packet_size, data_to_send))
        self.socket.sendto(pickle.dumps(packet), (self.host, self.port))
        # TODO: wait for the receiver to acknowledge the packet

        raise NotImplementedError()

    async def receive(self):
        """
        This function will receive a message from the socket.
        it sends an ACK packet to the sender.

        :return:
        """
        # Wait for the sender to send a packet
        data, addr = self.socket.recvfrom(self.max_packet_size)
        packet = pickle.loads(data)

        if packet.header.flags.data:
            for frame in packet.payload.frame_lst:
                if frame.stream_id in self.streams:
                    self.streams[frame.stream_id] += frame.data
                else:
                    self.streams[frame.stream_id] = frame.data

            # send an ACK packet to the sender
            packet.header.flags = PacketType.ACK_DATA.value
            packet.payload.frame_lst = []
            self.socket.sendto(pickle.dumps(packet), addr)

        if packet.header.flags.fin:
            self.close()  # TODO

    def close(self):

        # send a FIN packet to the peer
        packet = QUICPacket(PacketType.FIN)
        self.socket.sendto(pickle.dumps(packet), (self.host, self.port))

        # wait for the peer to send a FIN packet
        data, addr = self.socket.recvfrom(self.max_packet_size)
        packet = pickle.loads(data)

        if packet.header.flags.ACK:
            print("Connection closed successfully")

        # TODO: check what to do if the peer did not send an ACK packet
        raise NotImplementedError()


class QUICPacket:

    def __init__(self, PacketType: "PacketType"):
        self.header: "QUICHeader" = QUICPacket.QUICHeader(flags=PacketType.value)
        self.payload: "QUICPacket.Payload" = QUICPacket.Payload()

    def add_frame(self, frame: "QUICPacket.Frame"):
        self.payload.add_frame(frame)

    class Payload:
        def __init__(self):
            self.frame_lst: List[QUICPacket.Frame] = []

        def add_frame(self, frame: "QUICPacket.Frame"):
            self.frame_lst.append(frame)

    @dataclass
    class Frame:
        """
        This is the QUICStream class.
        It represents a stream in the QUIC protocol.
        Each stream has a unique identifier and data.
        """
        stream_id: int
        offset: int
        length: int
        data: bytes

    @dataclass
    class QUIQFlags:
        """
        This is the QUIQFlags class.
        It represents the flags used in the QUIC protocol.
        Each flag is a boolean value that indicates whether a certain feature is enabled or not.
        """
        syn: bool = field(default=False)
        ack: bool = field(default=False)
        data: bool = field(default=False)
        fin: bool = field(default=False)

    class QUICHeader:
        __packet_generator: int = 0

        def _calculate_connection_id(self, dst_port: str, dst_ip: str):
            # Connection ID will be the sum bits of dst port + dst ip
            raise NotImplementedError()

        def set_connection_id(self, dst_port: str, dst_ip: str):
            self.connection_id = self._calculate_connection_id(dst_port, dst_ip)
            return

        @staticmethod
        def generate_packet_number():
            QUICPacket.QUICHeader.__packet_generator += 1
            return QUICPacket.QUICHeader.__packet_generator

        def __init__(self, flags: "QUIQFlags"):
            self.flags = flags
            self.connection_id = None  # TODO: Generate connection ID
            self.packet_number = QUICPacket.QUICHeader.generate_packet_number()


class PacketType(Enum):
    SYN = QUICPacket.QUIQFlags(syn=True, ack=False, data=False, fin=False)
    ACCEPT_CONNECTION = QUICPacket.QUIQFlags(syn=True, ack=True, data=False, fin=False)
    ACK_DATA = QUICPacket.QUIQFlags(syn=False, ack=True, data=False, fin=False)
    DATA = QUICPacket.QUIQFlags(syn=False, ack=False, data=True, fin=False)
    FIN = QUICPacket.QUIQFlags(syn=False, ack=False, data=False, fin=True)


if __name__ == "__main__":
    packet_e = QUICPacket(PacketType.SYN, b"Hello, World!")
    print(packet_e.header.flags)
