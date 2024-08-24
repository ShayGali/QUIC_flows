from QUIC_api import *
import threading
import asyncio
import io
import sys

HOST = '127.0.0.1'
PORT = 4269
FILE_TO_SEND = "inputs/1mb_file.txt"
NUMBER_OF_STREAMS = 3


async def start_receiver():
    """
    This function is used to receive files from the sender and compare them with the original file
    :return: success message if all files are received successfully, error message otherwise
    """
    conn = QUIC()
    conn.listen(HOST, PORT)
    file_data = []
    while True:
        new_file_data = await conn.receive()
        if new_file_data is None:
            break
        file_data = new_file_data

    # check if the number of received files is equal to the number of streams
    if len(file_data) != NUMBER_OF_STREAMS:
        # return error in red color
        return "\033[91m" + "Error: Files are not equal" + "\033[0m"

    with open(FILE_TO_SEND, 'rb') as f1:
        original_data = f1.read()
        for file in file_data:
            if original_data != file:
                # return error in red color
                return "\033[91m" + "Error: Files are not equal" + "\033[0m"
    # return success in green color
    return "\033[92m" + "All files are received successfully" + "\033[0m"


async def start_sender():
    """
    This function is used to send files to the receiver
    """
    await asyncio.sleep(1)  # wait for the receiver to start listening
    with open(FILE_TO_SEND, "rb") as f:
        file_data = f.read()
        conn = QUIC()
        conn.connect_to(HOST, PORT)
        await conn.send_files([file_data] * NUMBER_OF_STREAMS)
        conn.close()


def run_async_function(func):
    """
    This function is used to run an async function in a synchronous way
    will change the stdout and stderr to io.StringIO() to avoid printing the output of the async function
    :param func: the async function to run
    :return:
    """

    # save the old stdout and stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    # change the stdout and stderr to io.StringIO()
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()

    try:  # run the async function
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(func())
        loop.close()
        return result
    finally:  # restore the old stdout and stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr


def main():
    receiver_result = None

    def run_receiver():
        nonlocal receiver_result
        receiver_result = run_async_function(start_receiver)

    def run_sender():
        run_async_function(start_sender)

    # run the receiver and sender in two different threads
    receiver_thread = threading.Thread(target=run_receiver)
    sender_thread = threading.Thread(target=run_sender)

    receiver_thread.start()
    sender_thread.start()

    # wait for the two threads to finish
    receiver_thread.join()
    sender_thread.join()

    # print the results
    print(receiver_result)


if __name__ == '__main__':
    main()
