#!/usr/bin/python           
#This is the server code
#Author Nikunj Shah
#Author Aparna Patil
import collections
import socket
import pickle
import random
import sys
import os

#Constant Declarations

#Values taken from the command line
SERVER_PORT = int(sys.argv[1])
FILE_NAME = sys.argv[2]
PACKET_LOSS_PROB = float(sys.argv[3])
N = int(sys.argv[4])

#Constant Declarations
TYPE_DATA = "0101010101010101"
TYPE_ACK  = "0011001100110011"
TYPE_NACK = "1100110011001100"
TYPE_EOF  = "1111111111111111"
DATA_PAD = "0000000000000000"
ACK_PORT = 65000
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
HOST_NAME = '0.0.0.0'
ACK_HOST_NAME = ''
server_socket.bind((HOST_NAME, SERVER_PORT))
last_received_packet=-1

#Server buffer that stores the incoming packets within the window
server_window_buffer = collections.OrderedDict()
#Maintains the window boundaries
window_minimum=0
window_maximum=N

#if file already exists, remove the file 
if os.path.isfile(FILE_NAME):
	os.remove(FILE_NAME)

#Will compute the checksum for the chunk of data provided
def compute_checksum_for_chuck(chunk,checksum):
	l=len(chunk)
	byte=0
	#Take 2 bytes of from the chunk data...takes 0xffff if the byte2 is not there because of odd chunk size
	while byte<l:
		byte1=ord(chunk[byte])
		shifted_byte1=byte1<<8
		if byte+1==l:
			byte2=0xffff
		else:
			byte2=ord(chunk[byte+1])
		#Merge the bytes in the form of byte1byte2 to make 16bits
		merged_bytes=shifted_byte1+byte2
		#Add to the 16 bit chekcsum computed till now
		checksum_add=checksum+merged_bytes
		#Compute the carryover
		carryover=checksum_add>>16
		#Compute the main part of the new checksum
		main_part=checksum_add&0xffff
		#Add the carryover to the main checksum again
		checksum=main_part+carryover
		#Do same for next 2 bytes
		byte=byte+2
	#Take 1's complement of the computed checksum and return it
	checksum_complement=checksum^0xffff
	return checksum_complement

#Check if checksum is proper
def is_checksum_proper(chunk,checksum):
	return compute_checksum_for_chuck(chunk,checksum)==0

#Drop packet based on random probability generated
def check_if_packet_drop(PACKET_LOSS_PROB,packet_sequence_number):
	return random.random()<PACKET_LOSS_PROB

#Send the ACK back to the sender
def send_acknowledgement(ack_number):
	ack_packet = pickle.dumps([ack_number, DATA_PAD, TYPE_ACK])
	ack_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	ack_socket.sendto(ack_packet,(ACK_HOST_NAME, ACK_PORT))
	ack_socket.close()

#Send the NACK back to the sender
def send_negative_acknowledgement(packet_sequence_number):
	nack_packet = pickle.dumps([packet_sequence_number, DATA_PAD, TYPE_NACK])
	nack_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	nack_socket.sendto(nack_packet,(ACK_HOST_NAME, ACK_PORT))
	nack_socket.close()	

#Write the data to the file
def write_data_to_file(packet_data):
	with open(FILE_NAME, 'ab') as file:
		file.write(packet_data)

#Main function
def main():
	global last_received_packet, ACK_HOST_NAME, window_minimum,window_maximum,server_window_buffer
	completed=False
	while not completed:
		#Receive data from the sender
		received_data1, addr = server_socket.recvfrom(65535)
		ACK_HOST_NAME = addr[0]
		received_data = pickle.loads(received_data1)
		packet_sequence_number, packet_checksum, packet_type, packet_data = received_data[0], received_data[1], received_data[2], received_data[3]
		#Check if the packet is last packet
		if packet_type == TYPE_EOF:
			completed=True
			server_socket.close()
		elif packet_type == TYPE_DATA:
			#Check if packet needs to be dropped due to probability
			drop_packet=check_if_packet_drop(PACKET_LOSS_PROB,packet_sequence_number)
			if drop_packet==True:
				print "Packet loss, sequence number = "+str(packet_sequence_number)
			else:
				#Check if the checksum is proper
				if is_checksum_proper(packet_data,packet_checksum):
					#Check if the packet is within the sliding window range
					if packet_sequence_number>=window_minimum and packet_sequence_number<=window_maximum:
						#If yes then buffer the packet data
						server_window_buffer[packet_sequence_number]=packet_data
						#If the packet causes a new continuous sequence to be formed at the start, then
						#write the data from those packets
						#shift the window
						#Send common ack for highest packet+1
						if packet_sequence_number==window_minimum:
							temp=packet_sequence_number
							while 1:
								if server_window_buffer.has_key(temp):
									window_minimum=window_minimum+1
									window_maximum=window_maximum+1
									write_data_to_file(server_window_buffer[temp])
									server_window_buffer.pop(temp)
									temp=temp+1
								else:
									break
							send_acknowledgement(temp)
						#Send the NACK's for the for all the not arrived packets before it
						else:
							temp=window_minimum
							while temp<=window_maximum:
								if server_window_buffer.has_key(temp):
									break
								else:
									send_negative_acknowledgement(temp)
									temp=temp+1
					#If the arrived packet is of sequence number greater than the window then send NACK's for the entire window
					elif packet_sequence_number>window_maximum:
						temp=window_minimum
						while temp<=window_maximum:
							send_negative_acknowledgement(temp)
							temp=temp+1
				else:
					print "Packet "+str(packet_sequence_number)+" has been dropped due to improper checksum"

if __name__ == "__main__":
    main()

