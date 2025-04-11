############################################################################
# (c) 2021-2021 Copyright, Real-Time Innovations. All rights reserved.
# No duplications, whole or partial, manual or electronic, may be made
# without express written permission. Any such copies, or revisions thereof, 
# must display this notice unaltered.
# This code contains trade secrets of Real-Time Innovations, Inc.
############################################################################

import os 
import argparse 
import threading
from posixpath import split 
from time import sleep
from os import error, path as os_path

file_path = os_path.dirname(os_path.realpath(__file__))
parser = argparse.ArgumentParser(description='DDS Chat Application')

parser.add_argument('user', help='User Name', type=str) 
parser.add_argument('group', help='Group Name', type=str)
parser.add_argument('-f', '--firstname', help='First Name', type=str, default='') 
parser.add_argument('-1', '--lastname', help='Last Name', type=str, default='')

args = parser.parse_args()

import rticonnextdds_connector as rti



with rti.open_connector(
    config_name="Chat_ParticipantLibrary::Chat_Participant",
    url= file_path + "/chat_app.xml"
) as connnector:
    
    sleep(200)