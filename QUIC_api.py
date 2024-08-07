import sys
import asyncio
from dataclasses import dataclass, field
from enum import Enum
import socket
import pickle
import random
import struct
from typing import Dict, List, Tuple

PACKET_DATA_SIZE = 60000
MAX_PACKET_SIZE = 65535


class QUIC:

    def __init__(self):
        # Create UDP socket
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 ** 20)
        # self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2 ** 20)
        self._is_closed = False

        # for later use
        self._host = None
        self._port = None

        self._stream_id_generator = 0
        self._input_streams: Dict[int, bytes] = {}  # a buffer to store the received data
        self._output_streams: Dict[int, bytes] = {}

    def listen(self, host: str, port: int):
        """
        This function will listen for incoming connection.
        :param host: The IP address to listen on.
        :param port: The port to listen on.
        :return:
        """
        print(f"Listening on {host}:{port}")

        self._host = host
        self._port = port

        # Bind the socket to the address
        self._socket.bind((self._host, self._port))

        # Wait for the client to send a SYN packet
        data, addr = self._socket.recvfrom(MAX_PACKET_SIZE)

        print(f"Connection request from {addr}")

        packet = pickle.loads(data)  # Deserialize the data

        # check if the client sent a SYN packet
        if packet.header.flags.syn:
            print(f"Received packet syn packet from {addr}")
            # Send an ACCEPT_CONNECTION packet to the client
            packet.header.flags = PacketType.ACCEPT_CONNECTION.value
            self._socket.sendto(pickle.dumps(packet), addr)
        else:  # If the client did not send a SYN packet
            # we assume that everything is ok, if not, we will raise an exception and stop the program of the receiver
            raise ConnectionError("The client did not send a SYN packet")

    def connect_to(self, host: str, port: int):
        """
        This function will connect to a receiver.

        :param host: Host address
        :param port: Port number
        :return:  None
        """
        self._host = host
        self._port = port

        # Send a SYN packet to the receiver so start the connection
        packet = _QUICPacket(PacketType.SYN)
        self._socket.sendto(pickle.dumps(packet), (self._host, self._port))

        # Wait for the receiver to accept the connection
        data, addr = self._socket.recvfrom(PACKET_DATA_SIZE)
        packet = pickle.loads(data)
        if packet.header.flags.syn and packet.header.flags.ack:
            print(f"Connection established with {addr}")
        else:
            # If the receiver did not accept the connection, raise an exception
            raise ConnectionError("The receiver did not accept the connection")

    async def send_files(self, data: List[bytes]) -> None:
        """
        This function will send a list of files (or part of some data in bytes format) to the receiver.
        The function will open a stream for each byte object in the list and send it to the receiver (asynchronously).
        :param data: A list of bytes objects.
        :return: None
        """
        for i, f in enumerate(data):
            self._output_streams[i + 1] = f

        await self._streams_send()
        self._output_streams.clear()  # clear the output_streams dictionary

        # send the DATA_FIN packet to the receiver
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Sending DATA_FIN packet~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        packet = _QUICPacket(PacketType.DATA_FIN)
        self._socket.sendto(pickle.dumps(packet), (self._host, self._port))

    async def _streams_send(self) -> None:
        """
        This function will send all the streams in the output_streams dictionary.
        :return: None
        """
        await asyncio.gather(
            *(self._send_on_stream(streemID) for streemID in self._output_streams)
        )

    async def _send_on_stream(self, stream_id: int):
        """
        This function will send the data on a specific stream.
        The function will split the data into frames and send them to the receiver.
        Run asynchronously between streams.
        :param stream_id:
        :return:
        """

        print(f"send on {stream_id}")

        # get the data from the output_streams dictionary
        data = self._output_streams[stream_id]
        # print(f"Sending data: {data}")
        # get a random frame size between 1000 and 2000 (excluding the frame header size)
        frame_size = int(random.uniform(1000, 2000))
        print(f"{stream_id=}, {frame_size=}")
        frame_data_length = frame_size - _QUICPacket.Frame.FRAME_HEADER_SIZE
        number_of_frames = len(data) // frame_data_length  # calculate the number of frames

        # check if you need an extra frame
        if len(data) % frame_data_length != 0:
            number_of_frames += 1

        # calculate the number of frames per packet
        frame_per_packet = PACKET_DATA_SIZE // frame_size
        offset = 0

        # calculate the number of packets
        number_of_packets = number_of_frames // frame_per_packet
        if number_of_frames % frame_per_packet != 0:
            number_of_packets += 1

        # create the packets and send
        for _ in range(number_of_packets):
            packet = _QUICPacket(PacketType.DATA)
            # add the frames to the packet
            for _ in range(frame_per_packet):
                if offset == number_of_frames - 1:  # if this is the last frame, we will add the remaining data and end the loop
                    data_to_send = data[offset * frame_data_length: len(data)]
                    packet.add_frame(_QUICPacket.Frame(stream_id, offset, frame_data_length, data_to_send))
                    break
                data_to_send = data[offset * frame_data_length: (offset + 1) * frame_data_length]
                packet.add_frame(_QUICPacket.Frame(stream_id, offset, frame_data_length, data_to_send))
                offset += 1

            # send the packet
            print(f"Sending packet on stream {stream_id}, number of packet: {packet.header.packet_number}")
            self._socket.sendto(pickle.dumps(packet), (self._host, self._port))
            # wait 0.001 seconds to simulate the network delay and accept the ACK packet
            await asyncio.sleep(0.1)

    async def receive(self) -> List[bytes] | None:
        """
        This function will receive a message from the socket.
        It sends an ACK packet to the sender.
        The data will be stored in the input_streams dictionary.
        :return: List of bytes objects, or None if the connection is closed.
        """
        num_of_packets = 0
        while True:
            # Wait for the sender to send a packet
            data, addr = self._socket.recvfrom(MAX_PACKET_SIZE)
            packet = pickle.loads(data)  # Deserialize the data
            num_of_packets += 1
            # if len(packet.payload.frame_lst) == 0:
            # print(f"Received packet : packet number: {packet.header.packet_number}, flags: {packet.header.flags} (got no frames)")
            # else:
            # print(f"Received packet : packet number: {packet.header.packet_number}, on stream: {packet.payload.frame_lst[0].stream_id}, flags: {packet.header.flags}, number of frames: {len(packet.payload.frame_lst)}")

            # if the packet is a data packet
            if packet.header.flags.data:
                if packet.header.flags.fin:
                    print("Received all the data")
                    break
                for frame in packet.payload.frame_lst:
                    # IMPORTANT!
                    # we assume that the frames are in order, and all the frames are received
                    # if data loss was an option, each frame offset would be considered.
                    if frame.stream_id in self._input_streams:
                        self._input_streams[frame.stream_id] += frame.data
                    else:
                        self._input_streams[frame.stream_id] = frame.data

                # send an ACK packet to the sender
                packet.header.flags = PacketType.ACK_DATA.value
                packet.payload.frame_lst = []
                self._socket.sendto(pickle.dumps(packet), addr)

            # if the packet is a close connection packet
            if packet.header.flags.fin:
                # close the connection
                self._socket.close()
                self._is_closed = True
                print(f"Number of packets: {num_of_packets}")
                print("Connection closed")
                return None

        print(f"Number of packets: {num_of_packets}")
        # TODO: statistics
        return self._build_files()

    def _build_files(self) -> List[bytes]:
        """
        This function will build the files from the input_streams dictionary.
        Will clear the input_streams dictionary.
        :return: A list of bytes objects.
        """
        # get the files from the input_streams dictionary
        files = list(self._input_streams.values())
        # clear the input_streams dictionary
        self._input_streams.clear()
        return files

    def close(self):
        """
        This function will close the connection.
        :return:
        """
        if self._is_closed:
            return

        # send a FIN packet to the peer
        packet = _QUICPacket(PacketType.FIN)
        self._socket.sendto(pickle.dumps(packet), (self._host, self._port))

        # IMPORTANT!
        # we assume that the peer gets the FIN packet and closes the connection

        # close the socket
        self._socket.close()
        self._is_closed = True
        print("Connection closed")


class _QUICPacket:

    def __init__(self, PacketType: "PacketType"):
        self.header: "QUICHeader" = _QUICPacket.QUICHeader(flags=PacketType.value)
        self.payload: "_QUICPacket.Payload" = _QUICPacket.Payload()

    def add_frame(self, frame: "_QUICPacket.Frame"):
        self.payload.add_frame(frame)

    def __str__(self):
        return ("QUICPacket(\n"
                f"Headers: {self.header.flags}\n"
                f"payload: {self.payload.frame_lst}"
                ")")

    class QUICHeader:
        __packet_generator: int = 0

        def __init__(self, flags: "QUIQFlags"):
            self.flags = flags
            self.packet_number = _QUICPacket.QUICHeader.generate_packet_number()

        @staticmethod
        def generate_packet_number():
            _QUICPacket.QUICHeader.__packet_generator += 1
            return _QUICPacket.QUICHeader.__packet_generator

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

    class Payload:
        """
        This is the QUICPayload class.
        Will hold a list of frames.
        """

        def __init__(self):
            self.frame_lst: List[_QUICPacket.Frame] = []

        def add_frame(self, frame: "_QUICPacket.Frame"):
            self.frame_lst.append(frame)

    @dataclass
    class Frame:
        """
        This is the QUICStream class.
        It represents a stream in the QUIC protocol.
        Each stream has a unique identifier and data.
        """
        FRAME_HEADER_SIZE = sys.getsizeof(int()) * 3
        stream_id: int
        offset: int  # The offset of the data in the stream
        data_length: int
        data: bytes


class SerializableQUICPacket:
    HEADER_FORMAT = '!BBIQ'  # 1 byte for flags, 1 byte for packet type, 4 bytes for packet number, 8 bytes for payload length
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    MAX_PAYLOAD_SIZE = 1452  # Assuming a typical MTU of 1500, subtracting 20 bytes for IP header and 8 bytes for UDP header
    _packet_number_counter = 0

    def __init__(self, packet_type: int, flags: int = 0):
        self.packet_type = packet_type
        self.flags = flags
        self.packet_number = self.generate_packet_number()
        self.payload = bytearray()

    @classmethod
    def generate_packet_number(cls):
        cls._packet_number_counter += 1
        return cls._packet_number_counter

    def add_frame(self, stream_id: int, offset: int, data: bytes):
        frame = struct.pack('!IIQ', stream_id, offset, len(data)) + data
        if len(self.payload) + len(frame) <= self.MAX_PAYLOAD_SIZE:
            self.payload.extend(frame)
        else:
            raise ValueError("Payload size exceeded")

    def serialize(self) -> bytes:
        header = struct.pack(self.HEADER_FORMAT, self.flags, self.packet_type, self.packet_number, len(self.payload))
        return header + self.payload

    @classmethod
    def deserialize(cls, data: bytes) -> Tuple['SerializableQUICPacket', List[Tuple[int, int, bytes]]]:
        header = struct.unpack(cls.HEADER_FORMAT, data[:cls.HEADER_SIZE])
        flags, packet_type, packet_number, payload_length = header

        packet = cls(packet_type, flags)
        packet.packet_number = packet_number
        packet.payload = bytearray(data[cls.HEADER_SIZE:cls.HEADER_SIZE + payload_length])

        frames = []
        offset = 0
        while offset < len(packet.payload):
            stream_id, frame_offset, data_length = struct.unpack_from('!IIQ', packet.payload, offset)
            offset += 16  # size of stream_id, frame_offset, and data_length
            frame_data = packet.payload[offset:offset + data_length]
            frames.append((stream_id, frame_offset, frame_data))
            offset += data_length

        return packet, frames

    def __str__(self):
        return f"SerializableQUICPacket(type={self.packet_type}, flags={self.flags}, number={self.packet_number}, payload_size={len(self.payload)})"


class PacketType(Enum):
    SYN = _QUICPacket.QUIQFlags(syn=True, ack=False, data=False, fin=False)
    ACCEPT_CONNECTION = _QUICPacket.QUIQFlags(syn=True, ack=True, data=False, fin=False)
    ACK_DATA = _QUICPacket.QUIQFlags(syn=False, ack=True, data=False, fin=False)
    DATA = _QUICPacket.QUIQFlags(syn=False, ack=False, data=True, fin=False)
    DATA_FIN = _QUICPacket.QUIQFlags(syn=False, ack=False, data=True, fin=True)
    FIN = _QUICPacket.QUIQFlags(syn=False, ack=False, data=False, fin=True)
