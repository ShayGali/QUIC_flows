import asyncio
from dataclasses import dataclass
from enum import IntEnum
import socket
import random
import struct
import time
from typing import Dict, List, Tuple


class QUIC:
    """
    This class represents a QUIC connection.
    You can use this class as a sender or a receiver.
    If you are the receiver, at the end of the `receive` function, a statistics will be displayed.
    """

    def __init__(self):
        # Create UDP socket
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._is_closed = False

        # for later use (so we can close the connection and open it again in the same instance)
        self._host = None
        self._port = None

        self._stream_id_generator = 0
        # a buffer to store the received data
        self._input_streams: Dict[int, bytes] = {}
        # a buffer to store the data that needs to be sent
        self._output_streams: Dict[int, bytes] = {}

        # the statistics of the connection
        self.total_connection_statistics: Stream_Statistics = Stream_Statistics(0, 0, 0, 0, 0, 0)
        # a dictionary to store the statistics of each stream
        self.stream_statistics: Dict[int, Stream_Statistics] = {}

    def listen(self, host: str, port: int):
        """
        This function will listen for incoming connection.
        :param host: The IP address to listen on.
        :param port: The port to listen on.
        :return:
        """
        print(f"Listening on {host}: {port}")

        self._host = host
        self._port = port

        # Bind the socket to the address
        self._socket.bind((self._host, self._port))

        # Wait for the client to send a SYN packet
        data, addr = self._socket.recvfrom(_QUICPacket.MAX_PACKET_SIZE)

        print(f"Connection request from {addr}")

        # Deserialize the data
        packet = _QUICPacket.deserialize(data)[0]

        # check if the client sent a SYN packet
        if packet.flags == QUIQ_Flags.SYN:
            print(f"Received packet syn packet from {addr}")
            # Send an ACCEPT_CONNECTION packet to the client
            packet.flags = QUIQ_Flags.ACCEPT_CONNECTION
            self._socket.sendto(packet.serialize(), addr)
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
        packet = _QUICPacket(QUIQ_Flags.SYN)
        self._socket.sendto(packet.serialize(), (self._host, self._port))

        # Wait for the receiver to accept the connection
        data, addr = self._socket.recvfrom(_QUICPacket.MAX_PACKET_SIZE)
        packet = _QUICPacket.deserialize(data)[0]
        if packet.flags == QUIQ_Flags.ACCEPT_CONNECTION:
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

        # send the data on the streams
        await self._streams_send()
        self._output_streams.clear()  # clear the output_streams dictionary

        # send the DATA_FIN packet to the receiver
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Sending DATA_FIN packet~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        packet = _QUICPacket(QUIQ_Flags.DATA_FIN)
        self._socket.sendto(packet.serialize(), (self._host, self._port))

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

        # get the data from the output_streams dictionary
        data = self._output_streams[stream_id]
        # print(f"Sending data: {data}")
        # get a random frame size between 1000 and 2000 (excluding the frame header size)
        frame_size = int(random.uniform(1000, 2000))
        frame_data_length = frame_size - _QUICPacket.FRAME_HEADER_SIZE  # calculate the frame data length
        number_of_frames = len(data) // frame_data_length  # calculate the number of frames

        # check if you need an extra frame
        if len(data) % frame_data_length != 0:
            number_of_frames += 1

        # calculate the number of frames per packet
        frame_per_packet = _QUICPacket.MAX_PAYLOAD_SIZE // frame_size
        offset = 0

        # calculate the number of packets
        number_of_packets = number_of_frames // frame_per_packet
        if number_of_frames % frame_per_packet != 0:
            number_of_packets += 1

        print(f"{stream_id=}, {number_of_packets=}, {frame_per_packet=}, {number_of_frames=}, {frame_size=}")

        # create the packets and send
        for i in range(number_of_packets):
            if i == 0:
                packet = _QUICPacket(QUIQ_Flags.STREAM_FIRST)
            elif i == number_of_packets - 1:
                packet = _QUICPacket(QUIQ_Flags.STREAM_LAST)
            else:
                packet = _QUICPacket(QUIQ_Flags.DATA)
            # add the frames to the packet
            for _ in range(frame_per_packet):
                if offset == number_of_frames - 1:  # if this is the last frame, we will add the remaining data and end the loop
                    data_to_send = data[offset * frame_data_length: len(data)]
                    packet.add_frame(stream_id, offset, data_to_send)
                    break
                data_to_send = data[offset * frame_data_length: (offset + 1) * frame_data_length]
                packet.add_frame(stream_id, offset, data_to_send)
                offset += 1

            self._socket.sendto(packet.serialize(), (self._host, self._port))

            # wait 0.001 seconds to simulate the network delay and accept the ACK packet
            await asyncio.sleep(0.001)

    async def receive(self) -> List[bytes] | None:
        """
        This function will receive a message from the socket.
        It sends an ACK packet to the sender.
        The data will be stored in the input_streams dictionary.
        :return: List of bytes objects, or None if the connection is closed.
        """
        while True:
            # Wait for the sender to send a packet
            data, addr = self._socket.recvfrom(_QUICPacket.MAX_PACKET_SIZE)
            packet, frames = _QUICPacket.deserialize(data)

            # if the packet is a data packet
            if packet.flags in range(QUIQ_Flags.DATA, QUIQ_Flags.DATA_FIN + 1):

                # NOTE: if we receive only one packet, we will not be able to calculate the time,
                # but it is not a problem because we will not consider the time of one packet
                # (it will be not accurate anyway)

                # we start measuring the time of the first frame of each stream
                if packet.flags == QUIQ_Flags.STREAM_FIRST:
                    start_time = time.time()
                    if frames[0].stream_id not in self.stream_statistics:  # need for continuous streams
                        self.stream_statistics[frames[0].stream_id] = Stream_Statistics(frames[0].stream_id, 0, 0, 0, 0,
                                                                                        0)
                    self.stream_statistics[frames[0].stream_id].time = start_time
                    self.total_connection_statistics.time = start_time

                # count the number of frames in each stream
                if len(frames) != 0:
                    self.stream_statistics[frames[0].stream_id].number_of_frames += len(frames)
                    self.total_connection_statistics.number_of_frames += len(frames)

                # if the packet is the last frame of the stream
                if packet.flags == QUIQ_Flags.STREAM_LAST:
                    end_time = time.time()
                    self.stream_statistics[frames[0].stream_id].time = (
                            end_time - self.stream_statistics[frames[0].stream_id].time
                    )

                if packet.flags == QUIQ_Flags.DATA_FIN:
                    # calculate the time it took to send all the data on all the streams
                    end_time = time.time()
                    self.total_connection_statistics.time = end_time - self.total_connection_statistics.time
                    print("Received all the data")
                    self.display_statistics()
                    break

                # update the statistics
                # sum the data length of the frames
                payload_size = packet.payload_length - len(frames) * _QUICPacket.FRAME_HEADER_SIZE
                # of the current stream
                self.stream_statistics[frames[0].stream_id].number_of_packets += 1
                self.stream_statistics[frames[0].stream_id].total_bytes += len(data)
                self.stream_statistics[frames[0].stream_id].payload_size += payload_size

                # of the total connection
                self.total_connection_statistics.number_of_packets += 1
                self.total_connection_statistics.total_bytes += len(data)
                self.total_connection_statistics.payload_size += payload_size

                for frame in frames:
                    # IMPORTANT!
                    # we assume that the frames are in order, and all the frames are received
                    # if data loss was an option, each frame offset would be considered.
                    if frame.stream_id in self._input_streams:
                        self._input_streams[frame.stream_id] += frame.data
                    else:
                        self._input_streams[frame.stream_id] = frame.data

                # send an ACK packet to the sender
                self._socket.sendto(_QUICPacket(QUIQ_Flags.ACK_DATA).serialize(), addr)

            # if the packet is a close connection packet
            if packet.flags == QUIQ_Flags.FIN:
                # close the connection
                self._socket.close()
                self._is_closed = True
                print("Connection closed")
                return None

        # return the files that were received in each stream
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
        # if the connection is already closed, return
        if self._is_closed:
            return

        # send a FIN packet to the peer
        packet = _QUICPacket(QUIQ_Flags.FIN)
        self._socket.sendto(packet.serialize(), (self._host, self._port))

        # IMPORTANT!
        # we assume that the peer gets the FIN packet and closes the connection

        # close the socket
        self._socket.close()
        self._is_closed = True
        print("Connection closed")

    def display_statistics(self) -> None:
        """
        Display the statistics of the connection as requested in the assignment.
        """
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Statistics~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n")

        print("All data statistics:")
        print(f"\t{'Number of streams':<25}: {len(self.stream_statistics):,}")
        print(f"\t{'Total Number of packets':<25}: {self.total_connection_statistics.number_of_packets:,}")
        print(f"\t{'Total Number of frames':<25}: {self.total_connection_statistics.number_of_frames:,}")
        print(f"\t{'Total Number of bytes':<25}: {self.total_connection_statistics.total_bytes:,}")
        print(f"\t{'Total Payload size':<25}: {self.total_connection_statistics.payload_size:,}")
        print(f"\t{'Total time':<25}: {self.total_connection_statistics.time:,} seconds")

        # d part
        avg_data_rate = self.total_connection_statistics.total_bytes / self.total_connection_statistics.time
        print(f"\t{'Average data rate':<25}: {avg_data_rate:,} bytes per second")

        # e part
        avg_packet_rate = self.total_connection_statistics.number_of_packets / self.total_connection_statistics.time
        print(f"\t{'Average packet rate':<25}: {avg_packet_rate:,} packets per second")

        print("\nEach stream statistics:")
        for stream_stat in self.stream_statistics.values():
            print(f"\tStream {stream_stat.stream_id:,} statistics:")
            print(f"\t\t{'Number of packets':<20}: {stream_stat.number_of_packets:,}")
            print(f"\t\t{'Number of frames':<20}: {stream_stat.number_of_frames:,}")
            print(f"\t\t{'Number of bytes':<20}: {stream_stat.total_bytes:,}")
            print(f"\t\t{'Payload size':<20}: {stream_stat.payload_size:,}")
            print(f"\t\t{'Time':<20}: {stream_stat.time:,} seconds")

            # c part
            avg_data_rate = stream_stat.total_bytes / stream_stat.time
            print(f"\t\t{'Average data rate':<20}: {avg_data_rate:,} bytes per second")

        print("\n~~~~~~~~~~~~~~~~~~~~~~~~~End of statistics~~~~~~~~~~~~~~~~~~~~~~~~~~")
        # TODO: show graphs of d and e on different number of streams


class _QUICPacket:
    """
    This class represents a QUIC packet.
    It uses fix size for the header and the frame header.
    """

    # a constant for the maximum packet size
    MAX_PACKET_SIZE = 15000

    # the format of the header
    HEADER_FORMAT = '!BIQ'  # 1 byte for flags, 4 bytes for packet number, 8 bytes for payload length
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    MAX_PAYLOAD_SIZE = MAX_PACKET_SIZE - HEADER_SIZE

    # the format of the frame
    FRAME_FORMAT = '!IIQ'  # 4 bytes for stream_id, 4 bytes for offset, 8 bytes for data length
    FRAME_HEADER_SIZE = struct.calcsize(FRAME_FORMAT)

    # class variable to generate the packet number
    _packet_number_gen = 0

    def __init__(self, flags: int = 0):
        self.flags = flags
        self.packet_number = self.generate_packet_number()
        self.payload_length = 0
        self.payload = bytearray()

    @classmethod
    def generate_packet_number(cls):
        cls._packet_number_gen += 1
        return cls._packet_number_gen

    def add_frame(self, stream_id: int, offset: int, data: bytes):
        """
        try to add a frame to the packet payload
        if the frame can't fit in the payload, raise an exception
        """
        # frame header + frame data.
        # (!IIQ - 4 bytes for stream_id, 4 bytes for offset, 8 bytes for data length)
        frame = struct.pack('!IIQ', stream_id, offset, len(data)) + data
        if len(self.payload) + len(frame) <= self.MAX_PAYLOAD_SIZE:
            # if we can fit the frame in the payload, add it
            self.payload_length += len(frame)
            self.payload.extend(frame)
        else:
            raise ValueError("Payload size exceeded")

    def serialize(self) -> bytes:
        """
        Serialize the packet to bytes.
        :return: The packet as bytes.
        """
        header = struct.pack(self.HEADER_FORMAT, self.flags, self.packet_number, len(self.payload))
        return header + self.payload

    @classmethod
    def deserialize(cls, data: bytes) -> Tuple['_QUICPacket', List['_QUICFrame']]:
        """
        Deserialize the bytes to a packet and frames.
        :param data: The bytes to deserialize.
        :return: A tuple of the packet and a list of frames.
        """
        header = struct.unpack(cls.HEADER_FORMAT, data[:cls.HEADER_SIZE])
        flags, packet_number, payload_length = header

        packet = cls(flags)
        packet.packet_number = packet_number
        packet.payload = bytearray(data[cls.HEADER_SIZE:cls.HEADER_SIZE + payload_length])
        packet.payload_length = payload_length

        # parse the payload to frames
        frames = []
        offset = 0  # offset in the payload (not of the frame)
        while offset < len(packet.payload):
            stream_id, frame_offset, data_length = struct.unpack_from('!IIQ', packet.payload, offset)
            offset += cls.FRAME_HEADER_SIZE  # the header size
            frame_data = packet.payload[offset:offset + data_length]
            frame = _QUICFrame(stream_id, frame_offset, data_length, frame_data)
            frames.append(frame)
            offset += data_length

        return packet, frames

    def __str__(self):
        return f"_QUICPacket(flags={self.flags}, number={self.packet_number}, payload_size={len(self.payload)})"


@dataclass
class _QUICFrame:
    """
    This class represents a QUIC frame.
    This class contains the stream_id, offset, and data of the frame.
    """
    stream_id: int
    offset: int
    data_length: int
    data: bytes

    def __len__(self):
        return len(self.data)


@dataclass
class Stream_Statistics:
    """
    This class represents the statistics for a stream.
    """
    stream_id: int
    number_of_packets: int
    number_of_frames: int
    total_bytes: int
    payload_size: int
    time: float


class QUIQ_Flags(IntEnum):
    """
    Enum for the flags of the QUIC packet.
    The range of ACK_DATA to DATA_FIN represents a data packet with different flags.
    """
    SYN = 1
    ACCEPT_CONNECTION = 2  # SYN-ACK
    ACK_DATA = 3
    DATA = 4
    STREAM_FIRST = 5  # for the statistics
    STREAM_LAST = 6  # for the statistics
    DATA_FIN = 7
    FIN = 8
