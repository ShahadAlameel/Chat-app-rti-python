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
import base64

file_path = os_path.dirname(os_path.realpath(__file__))
parser = argparse.ArgumentParser(description='DDS Chat Application')

parser.add_argument('user', help='User Name', type=str)
parser.add_argument('group', help='Group Name', type=str)
parser.add_argument('-f', '--firstname', help='First Name', type=str, default='')
parser.add_argument('-l', '--lastname', help='Last Name', type=str, default='')

args = parser.parse_args()

os.environ['user'] = str(args.user)
os.environ['group'] = str(args.group)

import rticonnextdds_connector as rti

lock = threading.RLock()
finish_thread = False
offline_message_queue = {}

# Queue the messages for offline users
def queue_message_for_user(from_user, to_user, message, file_data=None, file_name=None):
    global offline_message_queue

    with lock:
        # If the user is offline, queue the message
        if to_user not in offline_message_queue:
            offline_message_queue[to_user] = []

        offline_message_queue[to_user].append((from_user, message, file_data, file_name))
    print(f"Message queued for {to_user} from:{from_user}. Message: '{message}'")

# Deliver queued messages to the user when they come online
def deliver_queued_messages(user):
    global offline_message_queue, message_output

    with lock:
        if user in offline_message_queue:
            messages = offline_message_queue[user]
            for from_user, message, file_data, file_name in messages:
                print(f"Delivering message to {user} from {from_user}: {message}")

                # Send the queued message via DDS
                message_output.instance.set_string("fromUser", from_user)
                message_output.instance.set_string("toUser", user)
                message_output.instance.set_string("toGroup", "")  # Empty group if not needed
                message_output.instance.set_string("message", message)
                if file_data and file_name:
                    message_output.instance.set_string("fileData", file_data)
                    message_output.instance.set_string("fileName", file_name)
                else:
                    message_output.instance.set_string("fileData", "")
                    message_output.instance.set_string("fileName", "")

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
                if (sample.info['sample_state'] == "NOT_READ") and (sample.valid_data == False) and (sample.info['instance_state'] == "NOT_ALIVE_NO_WRITERS"):
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
                print("#New chat message from user: " + data['fromUser'] + ". Message: '" + data['message'] + "'")
                if data['fileName'] and data['fileData']:
                    print(f"#File received: {data['fileName']}")
                    # You can save the file here or display it
                    try:
                        file_data = base64.b64decode(data['fileData'])
                        with open(data['fileName'], 'wb') as f:
                            f.write(file_data)
                        print(f"#File saved as: {data['fileName']}")
                    except Exception as e:
                        print(f"Error saving file: {e}")

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
                        print("#username/group: " + data['username'] + "/" + data['group'])

        elif command.startswith("send "):
            destination = command.split(maxsplit=2)
            if len(destination) == 3:
                with lock:
                    message_output.instance.set_string("fromUser", user)
                    message_output.instance.set_string("toUser", destination[1])
                    message_output.instance.set_string("toGroup", destination[1])
                    message_output.instance.set_string("message", destination[2])
                    message_output.instance.set_string("fileData", "")
                    message_output.instance.set_string("fileName", "")

                    # Before sending, check if the user is offline
                    if destination[1] in offline_message_queue:
                        queue_message_for_user(user, destination[1], destination[2])  # Queue the message
                    else:
                        message_output.write()  # Send the message if the user is online

            else:
                print("Wrong usage. Use \"send user|group message\"\n")

        elif command.startswith("sendfile "):
            destination_file = command.split(maxsplit=2)
            if len(destination_file) == 3:
                destination = destination_file[1]
                file_path_send = destination_file[2]
                try:
                    with open(file_path_send, 'rb') as f:
                        file_data = base64.b64encode(f.read()).decode('utf-8')
                    file_name = os.path.basename(file_path_send)

                    with lock:
                        message_output.instance.set_string("fromUser", user)
                        message_output.instance.set_string("toUser", destination)
                        message_output.instance.set_string("toGroup", destination)
                        message_output.instance.set_string("message", f"File: {file_name}")
                        message_output.instance.set_string("fileData", file_data)
                        message_output.instance.set_string("fileName", file_name)

                        if destination in offline_message_queue:
                            queue_message_for_user(user, destination, f"File: {file_name}", file_data, file_name)
                        else:
                            message_output.write()

                except FileNotFoundError:
                    print(f"File not found: {file_path_send}")
                except Exception as e:
                    print(f"Error sending file: {e}")

            else:
                print("Wrong usage. Use \"sendfile user|group filepath\"\n")

        else:
            print("Unknown command\n")

with rti.open_connector(
    config_name="Chat_ParticipantLibrary::ChatParticipant",
    url=file_path + "/chat_app.xml") as connector:

    user_output = connector.get_output("ChatUserPublisher::ChatUser_Writer")
    message_output = connector.get_output("ChatMessagePublisher::ChatMessage_Writer")

    user_input = connector.get_input("ChatUserSubscription::ChatUser_Reader")
    message_input = connector.get_input("ChatMessageSubscription::ChatMessage_Reader")

    user_output.instance.set_string("username", args.user)
    user_output.instance.set_string("group", args.group)

    if args.firstname != "":
        user_output.instance.set_string("firstName", args.firstname)
    if args.lastname != "":
        user_output.instance.set_string("lastName", args.lastname)

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