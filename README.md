# Slackbot API Scripts for Delegate and Voter Notifications
A set of algorithms to analyze the blockchain and provide Slack notifications

## Notifications

- Missed Blocks

## Responses

- Height: Most common height accross peer nodes.
- Red Nodes: Delegates that are missing blocks.
- Delegate: Information about a certain delegate.

## Installation

```git clone https://github.com/DEADP0OL/LWF-SlackBot```

```cd LWF-SlackBot```

```apt-get install python3-pip```

```pip3 install pandas```

```pip3 install requests```

```pip3 install slackclient```

## Configuration

- slackapitoken: The apitoken assigned to your slackbot (ex: xoxb-############-###############)
- apinode: The public node url or ip address for api requests (default http://127.0.0.1:5500/)
- missedblockinterval: The number of consecutive missed blocks required to reissue a slack alert
- minmissedblocks: The number of consecutive missed blocks required for an initial slack alert
- channels: A list of channels to broadcast nofications on
- users: A list of users to send direct messages of notifications to

## Activation

### Notifications

Notifications can be scheduled via crontab

```crontab -e```

Add a line to run the notifications script regularly. The example below runs it every hour at the top of the hour

```0 * * * * cd LWF-SlackBot && python3 notifications.py && cd```

### Responses

Start the python script

```python3 slackbot.py```

To keep the python script running after closing the terminal run the following command

```nohup bash slackbot.sh &```

To end the python script run the following command

```pkill -f slackbot```
