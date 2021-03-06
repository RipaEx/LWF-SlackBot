import pandas as pd
import numpy as np
import requests
import json
import re
from slackclient import SlackClient
from collections import defaultdict

'''___________SETUP FUNCTIONS___________'''

def getconfigs(file):
    #extracts configs from JSON file
    configs = json.load(open(file))
    apitoken = configs.get("slackapitoken")
    url = configs.get("apinode")
    backup = configs.get("backupnodes")
    port=configs.get("port")
    blockinterval = configs.get("blockintervalnotification")
    minmissedblocks = configs.get("minmissedblocks")
    channelnames = configs.get("channels")
    usernames = configs.get("users")
    numdelegates = configs.get("numdelegates")
    return apitoken,url,backup,port,blockinterval,minmissedblocks,channelnames,usernames,numdelegates

def cleanurl(url,port):
    cleanitems=['https://','http://','/',':'+port]
    for i in cleanitems:
        url=url.replace(i,'')
    return url

def getusernames(file):
    #gets username mappings from the JSON file
    usernames=json.load(open(file))
    return usernames

'''___________NODE API FUNCTIONS___________'''

def getdelegates(url):
    #gets current delegates from the url node api
    delegates = pd.DataFrame(requests.get(url+'api/delegates?orderBy=vote').json()['delegates'])
    delegates['vote']=pd.to_numeric(delegates['vote'])
    return delegates

def getpeers(url):
    #gets current peers from the url node api
    peers = pd.DataFrame(requests.get(url+'api/peers').json()['peers'])
    return peers

def getstatus(url,backup,port,tol=1):
    """gets current height from the list of backup nodes"""
    backupheights={}
    for i in backup:
        try:
            backupheights[cleanurl(i,port)]='{:,.0f}'.format(getheight(i))
        except:
            backupheights[cleanurl(i,port)]='not available'
    try:
        peers=getpeers(url)
        total=len(peers)
        peers=peers[peers['status']=='OK']    #filters to connected peers
        connectedpeers=len(peers)
        peerheight=peers['height'].mode()[0]    #calculates the mode height from connected peers
        print(peerheight)
        consensus=round(len(peers[abs(peers['height']-peerheight)<=tol])/total*100,2) #calculates consensus from peer height
        backupheights['Peers: '+str(connectedpeers)]='{:,.0f}'.format(peerheight)
        backupheights['Consensus']='{:.1f}%'.format(consensus)
    except:
        connectedpeers='not available'
        peerheight='not available'
        consensus='not available'
        backupheights['Peers: '+connectedpeers]=peerheight
        backupheights['Consensus']=consensus
    backupheights=pd.DataFrame.from_dict(backupheights,orient='index')
    backupheights.columns = ['Height']
    return connectedpeers,peerheight,consensus,backupheights

def getheight(url):
    #gets current block height from the url node api
    height = requests.get(url+'api/blocks/getHeight').json()['height']
    return height

'''___________SLACK API FUNCTIONS___________'''

def getchannellist(apitoken):
    #gets a list of all channels in the slack team
    slack_client = SlackClient(apitoken)
    channellist=slack_client.api_call("channels.list",exclude_archived=1,exclude_members=1)['channels']
    return channellist

def getgrouplist(apitoken):
    #gets a list of all groups in the slack team
    slack_client = SlackClient(apitoken)
    grouplist=slack_client.api_call("groups.list",exclude_archived=1,exclude_members=1)['groups']
    return grouplist

def getchannelids(channelnames,apitoken):
    #gets channelids for specified channels in a slack team
    channelids={}
    channelnames=[v.lower() for v in channelnames]
    channellist=getchannellist(apitoken)
    grouplist=getgrouplist(apitoken)
    channellist=[v for v in channellist if str(v.get('name')).lower() in channelnames]
    grouplist=[v for v in grouplist if str(v.get('name')).lower() in channelnames]
    for name in channelnames:
        id=None
        for channel in channellist:
            if str(channel.get('name')).lower() == name.lower():
                id=channel.get('id')
        if id is None:
            for group in grouplist:
                if str(group.get('name')).lower() == name.lower():
                    id=group.get('id')
        channelids[name]=id
    return channelids

def getuserlist(apitoken):
    #gets a list of all users in the slack team
    slack_client = SlackClient(apitoken)
    userlist=slack_client.api_call("users.list")['members']
    return userlist

def getuserids(usernames,apitoken):
    #gets userids for specified usernames in a slack team userlist
    userids={}
    usernames=[v.lower() for v in usernames]
    userlist=getuserlist(apitoken)
    userlist=[v for v in userlist if (str(v.get('name')).lower() in usernames) or (str(v.get('real_name')).lower() in usernames) or (str(v['profile'].get('display_name')).lower() in usernames) ]
    for name in usernames:
        id=None
        for user in userlist:
            if (str(user.get('name')).lower() == name.lower()) or (str(user.get('real_name')).lower() == name.lower()) or (str(user['profile'].get('display_name')).lower() == name.lower()):
                id=user.get('id')
        userids[name]=id
    return userids

def getdmchannelid(userid,apitoken):
    #opens a slack channel for a direct message to a specified userid
    slack_client = SlackClient(apitoken)
    api_call = slack_client.api_call("im.open",user=userid)
    channel_id=api_call['channel']['id']
    return channel_id

def getallchannelids(channelids,userids,apitoken):
    #creates one list of channelids for channels and direct messages
    allchannelids=[]
    for user,userid in userids.items():
        if userid is not None:
            allchannelids.append(getdmchannelid(userid,apitoken))
    for channel,channelid in channelids.items():
        if channelid is not None:
            allchannelids.append(channelid)
    return allchannelids

'''__________NOTIFICATION FUNCTIONS___________'''

def processdelegates(delegatesnew,delegates):
    """compares the current and previous delegate block counts to track consecutive missed/produced blocks"""
    delegatesnew['missedblocksmsg']=0
    if delegates is None:
        #if no previous delegate block counts are available, start missed/produced block counters at 0
        delegatesnew['newmissedblocks']=0
        delegatesnew['newproducedblocks']=0
        return delegatesnew
    else:
        delegates.rename(columns={'missedblocks': 'missedold','producedblocks':'producedold','missedblocksmsg':'msgold'}, inplace=True)
        delegates=delegates[['username','missedold','producedold','newmissedblocks','newproducedblocks','msgold']]
        delegatesnew=pd.merge(delegatesnew,delegates,how='left',on='username')
        delegatesnew['missedblocksmsg']=np.maximum(0,delegatesnew['missedblocksmsg']+delegatesnew['msgold'])
        delegatesnew['newmissedblocks']=np.maximum(0,delegatesnew['newmissedblocks']+delegatesnew['missedblocks']-delegatesnew['missedold'])
        #resets consecutive produced block counter to 0 if a delegate misses a block
        delegatesnew.loc[delegatesnew['missedblocks']-delegatesnew['missedold']>0, ['newproducedblocks']] = 0
        delegatesnew['newproducedblocks']=np.maximum(0,delegatesnew['newproducedblocks']+delegatesnew['producedblocks']-delegatesnew['producedold'])
        #resets consecutive missed block counter to 0 if a delegate produces a block
        delegatesnew.loc[delegatesnew['producedblocks']-delegatesnew['producedold']>0, ['newmissedblocks','missedblocksmsg']] = 0
        #resets all counters to 0 if a delegate begins forging
        delegatesnew.loc[delegatesnew['newmissedblocks'].isnull(), ['newmissedblocks','missedblocksmsg','newproducedblocks']] = 0
        #drops temporary columns
        delegatesnew=delegatesnew.drop(['missedold','producedold','msgold'],axis=1)
        return delegatesnew

def checknames(name):
    #creates a list of delegate name variations to compare with slack names
    names=[]
    names.append(name.lower())
    modifications={'_voting':'','_pool':''}
    for x,y in modifications.items():
        if x in name.lower():
            names.append(name.replace(x,y))
    return names

def makemissedblockmsglist(delegates,blockinterval,minmissedblocks,includeprevious=False):
    #creates a list of delegates that have missed blocks
    #when includeprevious is False, it will only include delegates that have either not previously been notified or have exceeded the blockinterval
    missedblockmsglist=[]
    for index, row in delegates.loc[delegates['newmissedblocks']>=minmissedblocks].iterrows():
        if includeprevious is False:
            if (row['newmissedblocks']>row['missedblocksmsg'])and((row['missedblocksmsg']<=1)or(row['newmissedblocks']-row['missedblocksmsg']>blockinterval)):
                missedblockmsglist.append({"username":row['username'],"missedblocksmsg":row['newmissedblocks']})
        else:
            missedblockmsglist.append({"username":row['username'],"missedblocksmsg":row['newmissedblocks']})
    for i in missedblockmsglist:
        delegates.loc[delegates['username']==i["username"], ['missedblocksmsg']] = i["missedblocksmsg"]
    return delegates,missedblockmsglist

def modifymissedblockmsglist(missedblockmsglist,slacknames,userlist):
    #modifies the list of users to notify to ping their slack username and id
    newmissedblockmsglist=[]
    for i in missedblockmsglist:
        delegate=i["username"]
        display=''
        name=''
        names=checknames(delegate)
        for j in slacknames:
            if delegate == j["delegate"]:
                names.append(str(j["slackname"]).lower())
        for x in [v for v in userlist if (str(v.get('name')).lower() in names) or (str(v.get('real_name')).lower() in names) or (str(v['profile'].get('display_name')).lower() in names) ]:
            name="<@"+x.get('id')+">"
            if x['profile'].get('display_name') is None:
                display=x.get('name')
            else:
                display=x['profile'].get('display_name')
        if str(display).lower()==delegate:
            i["username"]=name + ' '
        else:
            i["username"]=delegate + ' ' + name + ' '
        newmissedblockmsglist.append(i)
    return newmissedblockmsglist

def makemissedblockmsg(missedblockmsglist,blockinterval=0,includeprevious=False):
    #creates a message to notify delegates of missed blocks
    #when includeprevious is False, it will only include delegates that have either not previously been notified or have exceeded the blockinterval
    if includeprevious is False:
        message=""
        for i in missedblockmsglist:
            if message!="":
                message=message+"\n"
            if i["missedblocksmsg"]>blockinterval:
                message=message+i["username"] +"still red :small_red_triangle_down:"
            elif i["missedblocksmsg"]>1:
                message=message+i["username"] +"red :small_red_triangle_down:"
            else:
                message=message+i["username"] +"yellow :warning:"
    else:
        redmessage=":small_red_triangle_down: "
        yellowmessage=":warning: "
        for i in missedblockmsglist:
            if i["missedblocksmsg"]>1:
                if redmessage != ":small_red_triangle_down: ":
                    redmessage+=", "+i["username"]
                else:
                    redmessage+=i["username"]
            else:
                if yellowmessage != ":warning: ":
                    yellowmessage+=", "+i["username"]
                else:
                    yellowmessage+=i["username"]
        redmessage+=":small_red_triangle_down:"
        yellowmessage+=":warning:"
        if redmessage != ":small_red_triangle_down: :small_red_triangle_down:":
            message=redmessage
            if yellowmessage != ":warning: :warning:":
                message+="\n"+yellowmessage
        elif yellowmessage != ":warning: :warning:":
            message=yellowmessage
    return message

'''__________RESPONSE FUNCTIONS___________'''

def printdelegates(delegates,rank,limit):
    """outputs the delegates list in a friendly format"""
    delegates=delegates.loc[(delegates['rate']>=rank-limit)&(delegates['rate']<=rank+limit)]
    delegates['vote'] = delegates['vote']/100000000
    delegates['voteweight'] = (delegates['vote']/1000).map('{:,.3f}'.format).astype(str) + 'K'
    delegates['productivity'] = delegates['productivity'].map('{:,.2f}%'.format)
    delegates['approval'] = delegates['approval'].map('{:,.2f}%'.format)
    ind=(delegates['rate'].values.tolist()).index(rank)
    delegates=insertblankrow(delegates,ind+1)
    cleandelegates=delegates[['rate','username','approval','voteweight']].to_string(index=False)
    return cleandelegates

def insertblankrow(df,ind):
    """inserts a blank row into a dataframe at the specified index"""
    cols=list(df.columns.values)
    blank=pd.Series(['' for i in cols],index=cols)
    result=df.iloc[:ind].append(blank,ind)
    result=result.append(df.iloc[ind:],ind)
    return result
