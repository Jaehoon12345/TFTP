#!/usr/bin/python3
import os
import sys
import socket
import argparse
from struct import pack, unpack

DEFAULT_PORT = 3333
BLOCK_SIZE = 512
DEFAULT_TRANSFER_MODE = 'octet'

OPCODE = {'RRQ': 1, 'WRQ': 2, 'DATA': 3, 'ACK': 4, 'ERROR': 5}
ERROR_CODE = {
    0: "Not defined, see error message (if any).",
    1: "File not found.",
    2: "Access violation.",
    3: "Disk full or allocation exceeded.",
    4: "Illegal TFTP operation.",
    5: "Unknown transfer ID.",
    6: "File already exists.",
    7: "No such user."
}


# RRQ (Read Request) 메시지 전송
def send_rrq(filename, mode, sock, server_address):
    format = f'>h{len(filename)}sB{len(mode)}sB'
    rrq_message = pack(format, OPCODE['RRQ'], filename.encode(), 0, mode.encode(), 0)
    sock.sendto(rrq_message, server_address)


# WRQ (Write Request) 메시지 전송
def send_wrq(filename, mode, sock, server_address):
    format = f'>h{len(filename)}sB{len(mode)}sB'
    wrq_message = pack(format, OPCODE['WRQ'], filename.encode(), 0, mode.encode(), 0)
    sock.sendto(wrq_message, server_address)


# ACK 메시지 전송
def send_ack(block_num, sock, server_address):
    ack_message = pack('>hh', OPCODE['ACK'], block_num)
    sock.sendto(ack_message, server_address)


# 파일 다운로드 (GET)
def get_file(filename, sock, server_address):
    send_rrq(filename, DEFAULT_TRANSFER_MODE, sock, server_address)

    file = open(filename, 'wb')
    expected_block_number = 1

    while True:
        try:
            data, server = sock.recvfrom(516)
            opcode = int.from_bytes(data[:2], 'big')

            if opcode == OPCODE['DATA']:
                block_number = int.from_bytes(data[2:4], 'big')
                file_block = data[4:]

                if block_number == expected_block_number:
                    file.write(file_block)
                    send_ack(block_number, sock, server)
                    expected_block_number += 1

                if len(file_block) < BLOCK_SIZE:
                    print("File transfer completed.")
                    break

            elif opcode == OPCODE['ERROR']:
                error_code = int.from_bytes(data[2:4], 'big')
                print(f"Error {error_code}: {ERROR_CODE[error_code]}")
                file.close()
                os.remove(filename)
                break

        except socket.timeout:
            print("Timeout occurred. No response from server.")
            file.close()
            os.remove(filename)
            sys.exit(1)

    file.close()


# 파일 업로드 (PUT)
def put_file(filename, sock, server_address):
    if not os.path.exists(filename):
        print("Error: File does not exist.")
        sys.exit(1)

    send_wrq(filename, DEFAULT_TRANSFER_MODE, sock, server_address)
    file = open(filename, 'rb')
    block_number = 0

    while True:
        file_block = file.read(BLOCK_SIZE)
        block_message = pack(f'>hh{len(file_block)}s', OPCODE['DATA'], block_number + 1, file_block)
        sock.sendto(block_message, server_address)

        try:
            ack, server = sock.recvfrom(516)
            ack_opcode = int.from_bytes(ack[:2], 'big')
            ack_block_number = int.from_bytes(ack[2:4], 'big')

            if ack_opcode == OPCODE['ACK'] and ack_block_number == block_number + 1:
                block_number += 1
            else:
                print("Unexpected ACK received. Resending...")

        except socket.timeout:
            print("Timeout occurred while waiting for ACK. Resending...")

        if len(file_block) < BLOCK_SIZE:
            print("File transfer completed.")
            break

    file.close()


# 명령줄 인자 처리
parser = argparse.ArgumentParser(description='TFTP client program')
parser.add_argument('host', help="Server IP address")
parser.add_argument('operation', help="get or put a file", choices=['get', 'put'])
parser.add_argument('filename', help="Name of file to transfer")
parser.add_argument('-p', '--port', type=int, help="Server port (default: 69)", default=DEFAULT_PORT)
args = parser.parse_args()

server_address = (args.host, args.port)

# UDP 소켓 생성 및 타임아웃 설정
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(5)

# 클라이언트 동작 수행
if args.operation == 'get':
    get_file(args.filename, sock, server_address)
elif args.operation == 'put':
    put_file(args.filename, sock, server_address)

sock.close()
