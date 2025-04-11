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

os.environ['user'] = str(args.user)
os.environ['group'] = str(args.group)

import rticonnextdds_connector as rti

lock = threading.RLock()
finish_thread = False
offline_message_queue = {}

# Queue the messages for offline users
def queue_message_for_user(from_user, to_user, message):
    global offline_message_queue

    with lock:
        # If the user is offline, queue the message
        if to_user not in offline_message_queue:
            offline_message_queue[to_user] = []
        
        offline_message_queue[to_user].append((from_user, message))
    print(f"Message queued for {to_user} from:{from_user}. Message: '{message}'")

# Deliver queued messages to the user when they come online
def deliver_queued_messages(user):
    global offline_message_queue, message_output

    with lock:
        if user in offline_message_queue:
            messages = offline_message_queue[user]
            for from_user, message in messages:
                print(f"Delivering message to {user} from {from_user}: {message}")

                # Send the queued message via DDS
                message_output.instance.set_string("fromUser",from_user)  
                message_output.instance.set_string("toUser", user)  
                message_output.instance.set_string("toGroup", "")  # Empty group if not needed
                message_output.instance.set_string("message", message)  

                message_output.write() 
                sleep(3)

            # After delivering messages, clear the queue for the user
            offline_message_queue[user] = []

def user_subscriber_task(user_input):
    global finish_thread

    while finish_thread == False:
        try:
            user_input.wait(500)
        except rti.TimeoutError as error:
            continue
        
        with lock:
            user_input.read()
            for sample in user_input.samples:
                if(sample.info['sample_state'] == "NOT_READ") and (sample.valid_data == False) and (sample.info['instance_state'] == "NOT_ALIVE_NO_WRITERS"):
                    data = sample.get_dictionary()
                    print("#Dropped user: " + data['username'])
                    offline_message_queue[data['username']] = []  # Initialize the queue for offline user
                elif(sample.info['instance_state'] == "ALIVE"):
                    # User is online, deliver any queued messages
                    data = sample.get_dictionary()
                    if data['username'] in offline_message_queue:
                        print(f"#User {data['username']} is online. Delivering queued messages.")
                        deliver_queued_messages(data['username'])


def message_subscriber_task(message_input):
    global finish_thread

    while finish_thread == False:
        try:
            message_input.wait(500)
        except rti.TimeoutError as error:
            continue

        with lock:
            message_input.take()
            for sample in message_input.samples.valid_data_iter:
                data = sample.get_dictionary()
                print("#New chat message from user: "+ data['fromUser'] + ". Message: '" + data['message'] + "'")

def command_task(user, message_output, user_input):
    global finish_thread  

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

        elif command.startswith("send "):
            destination = command.split(maxsplit=2)
            if len(destination) == 3:
                with lock:
                    message_output.instance.set_string("fromUser", user)
                    message_output.instance.set_string("toUser", destination[1])
                    message_output.instance.set_string("toGroup", destination[1])
                    message_output.instance.set_string("message", destination[2])

                    # Before sending, check if the user is offline
                    if destination[1] in offline_message_queue:
                        queue_message_for_user(user, destination[1], destination[2])  # Queue the message
                    else:
                        message_output.write()  # Send the message if the user is online

                    #message_output.write()

            else:
                print("Wrong usage. Use \"senf user|group message\"\n")

        else:
            print("Unknown command\n")

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

    t1 = threading.Thread(target=command_task, args=(args.user, message_output, user_input,))
    t1.start()

    t2 = threading.Thread(target=message_subscriber_task, args=(message_input,))
    t2.start()

    t3 = threading.Thread(target=user_subscriber_task, args=(user_input,))
    t3.start()

    t1.join()
    t2.join()
    t3.join()

    #sleep(5)

    # unregister user
    user_output.instance.set_string("username", args.user)
    user_output.write(action="unregister")