#!/usr/bin/env python3

import time
from functions import *

#obtain config variables and initiate slack client
apitoken,url,backup,port,blockinterval,minmissedblocks,channelnames,usernames,numdelegates=getconfigs('config.json')
slack_client = SlackClient(apitoken)
slacknames=getusernames('slacknames.json')
userlist=getuserlist(apitoken)
delegatecsv='delegates.csv'

# slackbot unique constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
PREFIX="!"
EXAMPLE_COMMAND = ""
HELP_COMMAND=""
command_dict = {PREFIX+'help':"Describes the bot and it's available commands.",
            PREFIX+'delegate (<username> or <rank>)':'Provides information of a delegate. Defaults to rank 101.',
            PREFIX+'red nodes':'Lists delegates that are currently missing blocks.',
            PREFIX+'height':'Provides the current height accross specified nodes.'
            }
commands = [command+', ' for command in command_dict]
for key, value in command_dict.items():
    EXAMPLE_COMMAND += key+', '
    if key != PREFIX+'help':
        HELP_COMMAND += "*_"+key+"_*"+'\n'
        HELP_COMMAND += "     "+value+'\n'
EXAMPLE_COMMAND = EXAMPLE_COMMAND.rstrip(', ')
HELP_COMMAND = HELP_COMMAND.rstrip('\n')
PREFIX_REGEX = "^"+PREFIX+"([^\s]*)\s?([^\s]*)"

def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If that is also not found this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            command1, command2 = parse_calls(event["text"],PREFIX_REGEX)
            if command1 is not None:
                return command1, command2, event["channel"]
    return None, None, None

def parse_calls(message_text,REGEX):
    """
        Runs a regex search and returns the first two groups.
        Returns None,None if regex search criteria are not met.
    """
    matches = re.match(REGEX, message_text)
    return (matches.group(1), matches.group(2)) if matches else (None, None)

def handle_command(command1,command2,channel):
    """
        Determines an appropriate response for the determined command and replies on the channel.
    """
    # help response
    if command1.lower()=='help':
        response = "{}.".format(HELP_COMMAND)
    # red nodes response
    elif command1.lower()=='red':
        delegates = pd.read_csv("delegates.csv",index_col=0)
        delegates,missedblockmsglist=makemissedblockmsglist(delegates,0,1,True)
        if len(missedblockmsglist)>0:
            missedblockmsglist=modifymissedblockmsglist(missedblockmsglist,slacknames,userlist)
            response=makemissedblockmsg(missedblockmsglist,0,True)
        else:
            response = "No red nodes"
    # height response
    elif command1.lower()=='height':
        connectedpeers,peerheight,consensus,backupheights=getstatus(url,backup,port)
        response="```\n"+repr(backupheights)+"\n```"
    # delegate response
    elif command1.lower()=='delegate':
        delegate=command2
        limit=3
        try:
            delegates = pd.read_csv(delegatecsv,index_col=0)
            if (delegate is None) or (delegate==''):
                delegate=str(numdelegates)
            if not delegate.isdigit():
                if delegate.lower() in delegates['username'].str.lower().values:
                    rank=delegates.loc[delegates['username'].str.lower() == delegate.lower(), 'rate'].iloc[0]
                    response="```\n"+printdelegates(delegates,rank,limit)+"\n```"
                else:
                    response='Cannot find that delegate'
            else:
                rank=int(delegate)
                if rank in delegates['rate'].values:
                    response="```\n"+printdelegates(delegates,rank,limit)+"\n```"
                else:
                    response='Cannot find that delegate rank'
        except:
            response="Unknown Error"
    # default response for unknown commands
    else:
        #response = "Not sure what you mean. Try *{}*.".format(EXAMPLE_COMMAND)
        response = None
    # Sends the response back to the channel
    if response is not None:
        slack_client.api_call(
            "chat.postMessage",
            channel=channel,
            text=response or default_response,
            as_user=True
        )

if __name__ == "__main__":
    while True:
        if slack_client.rtm_connect(with_team_state=False):
            print("Starter Bot connected and running!")
            # Read bot's user ID by calling Web API method `auth.test`
            #starterbot_id = slack_client.api_call("auth.test")["user_id"]
            while True:
                command1,command2, channel = parse_bot_commands(slack_client.rtm_read())
                if command1 is not None:
                    handle_command(command1,command2, channel)
                time.sleep(RTM_READ_DELAY)
        else:
            print("Connection failed. Retrying...")
            time.sleep(RTM_READ_DELAY*5)
