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

lock = threading.RLock()

def command_task(user_input):
    finish_thread = False

    while finish_thread == False:
        command = input("Please enter command \n")

        if command == "exit":
            finish_thread = True
        elif command == "list":
            with lock:
                user_input.read()
                # printing list of users/groups
                for sample in user_input.samples.valid_data_iter:
                    # detecting alive instances
                    if sample.info['instance_state'] == 'ALIVE':
                        data = sample.get_dictionary()
                        print("#username/group: " + data['username']+ "/" + data['group'])

with rti.open_connector(
    config_name="Chat_ParticipantLibrary::ChatParticipant",
    url= file_path + "/chat_app.xml") as connector:

    user_output = connector.get_output("ChatUserPublisher::ChatUser_Writer")
    message_output = connector.get_output("ChatMessagePublisher::ChatMessage_Writer")


    user_input = connector.get_input("ChatUserSubscription::ChatUser_Reader")
    message_input = connector.get_input("ChatMessageSubscription::ChatMessage_Reader")

    user_output.instance.set_string("username", args.user)
    user_output.instance.set_string("group", args.group)

    if args.firstname != "":
        user_output.instance.set_string("firstName", args.firstName)
    if args.lastname != "":
        user_output.instance.set_string("lastName", args.lastName)
        
    user_output.write()

    t1 = threading.Thread(target=command_task, args=(user_input,))
    t1.start()

    t1.join()

    #sleep(5)

    # unregister user
    user_output.instance.set_string("username", args.user)
    user_output.write(action="unregister")