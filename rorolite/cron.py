"""Setup cron jobs.
"""
from __future__ import print_function
import os
import sys
import yaml
import re

# crontab format
# ┌───────────── minute (0 - 59)
# │ ┌───────────── hour (0 - 23)
# │ │ ┌───────────── day of month (1 - 31)
# │ │ │ ┌───────────── month (1 - 12)
# │ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)
# │ │ │ │ │              7 is also Sunday on some systems)
# │ │ │ │ │
# │ │ │ │ │
# * * * * *  command to execute


class Cron:
    keywords = ['min(ute)?s?', 'hours?', '', 'months?', '']
    skipWords=['min','minute','minutes''every','day','at','on','everyday','month','hour','months','hours','daily']
    daysAndMonths={
    3 : ['','january','february','march','april','may','june','july','august','septemeber','october','november','december'],
    4 : ['sunday', 'monday', 'tuesday', 'wednsday', 'thursday', 'friday', 'saturday']}
    valRegex=['([0-9]+):([0-9]+)\s*([apAP][mM])?','([0-9]+):?([0-9]+)?\s*([apAP][mM])','([0-3]?[0-9])(st|th|rd)']
    limits = [[0,59], [0,23], [1,31], [1,12], [0,6]]
    maxValues = [60, 24, 31, 12, 7]
    
    def __init__(self, directory="."):
        self.directory = directory
        self.config = self.read_config(directory)
        self.cronstrings = []

    def read_config(self, root):
        path = os.path.join(root, "rorolite.yml")
        return yaml.safe_load(open(path).read())
    def setup_cron(self):
        self.parse_cron()
        finalcronstr='\n'.join(self.cronstrings)
        os.system("crontab -l > .ctab")
        os.system("echo \""+finalcronstr+"\" >> .ctab")
        os.system("crontab .ctab")
    def parse_cron(self):
        if 'cron' in self.config:
            for job in self.config['cron']:
                cronstr=['*']*5
                cronval=[-1]*5
                tokens=[]
                jobstr=[]
                for token in job['when'].split(' '):
                    tokens.append(self.value_of(token))
                self.process_tokens(tokens,cronstr,cronval)
                for i in range(len(cronstr)):
                    x=(str(int(cronval[i])) if cronval[i]!=-1 else '')
                    y=(cronstr[i] if (x == '') or cronstr[i]!='*' else ''  )
                    jobstr.append(y+x)
                jobstr=' '.join(jobstr)
                print("\nrun %s at %s => %s"%(job['command'],job['when'],jobstr))
                self.cronstrings.append(jobstr+" "+job['command'])
    
    def in_limits(self,val,kwIndex):
        try:
            if val>=self.limits[kwIndex][0] and val<=self.limits[kwIndex][1]:
                return True
        except Exception as e:
            print("in_limits:",str(e))
        return False

    def key_word_index(self,str):
        for i in range(len(self.keywords)):
            if re.search(self.keywords[i],str,re.I):
                return i
        return False

    def is_type(self,type,val):
        value=None
        try:
            value=type(val)
        except Exception:
            return False
        return True

    def split_float(self,flVal,baseVal):
        temp=float(flVal)*float(baseVal)
        return (int(temp/baseVal),int(temp%baseVal))

    def value_of(self,val):
        try:
            if self.is_type(float,val):
                return float(val)
            for regex in self.valRegex:
                g=re.search(regex,val)
                if g and g.group():
                    return g.groups()
        except Exception as e:
            print("Exception at self.value_of with %r %r"%(val,e))
        return val
    def assign_cv(self,cronvals,cronstr,i,val,every=False):
        "every is used for specifying  every x format."
        if (i==len(cronvals)-1 and (val is float)) or (i<0):
            return
        if i<len(cronvals) and val>=self.limits[i][0]:
            val=int(val)
            if every and val>0:
                cronstr[i]='*/'
            if(cronvals[i]==-1):
                cronvals[i]=val
                for k in range(i):
                    cronvals[k]=(self.limits[k][0] if cronvals[k]==-1 else cronvals[k])
            else:
                cronvals[i]+=val

    def process_tokens(self,tokens,cronstr,cronvals):
        for i in range(len(tokens)):
            currentToken=tokens[i]
            if type(currentToken) is float and i+1<len(tokens):
                # 'every x' format
                try:
                    kwIndex=self.key_word_index(tokens[i+1])
                    if (kwIndex is not None) and currentToken>=self.limits[kwIndex][0]:
                        maxval=(self.maxValues[kwIndex-1] if kwIndex>0 else 1)
                        x,y=self.split_float(currentToken,maxval) # 2.5 hours => 2 hours 30 mins
                        self.assign_cv(cronvals,cronstr,kwIndex,x%self.maxValues[kwIndex],True)
                        self.assign_cv(cronvals,cronstr,kwIndex+1,x/self.maxValues[kwIndex],True)
                        if y>0:
                            self.assign_cv(cronvals,cronstr,kwIndex-1,y,True)
                except Exception as e:
                    print('Error processing %s %r on line %r'%(currentToken,e,sys.exc_info()[-1].tb_lineno))
            elif type(currentToken) is str:
                if currentToken in self.skipWords : # skip day, everyday,month etc
                    continue
                for key,value in self.daysAndMonths.items():
                    for k in range(len(value)):
                        if currentToken.lower() in value[k]: # apr,april,wed,wednsday etc. are valid
                            try:
                                cronvals[int(key)]=k
                                #lookForDayOfMonth(tokens,i-1)
                                #lookForDayOfMonth(tokens,i+1)
                            except Exception as e:
                                print(str(e))
            elif type(currentToken) is tuple:
                temp=currentToken
                temp=[(int(e) if self.is_type(int,e) else e)  for e in temp]
                temp=[(0 if e is None else e)  for e in temp]
                currentToken=tuple(temp)
                if len(currentToken)==3: #time
                    currentToken=(currentToken[1], currentToken[0], currentToken[2])
                    for v in range(len(currentToken)-1):
                        if self.in_limits(currentToken[v],v):
                            cronvals[v]=currentToken[v]
                    amPmStr=currentToken[len(currentToken)-1]
                    if amPmStr and amPmStr.lower() == 'pm':
                        cronvals[1]=(cronvals[1]+12)%24
                elif len(currentToken)==2:
                    if self.in_limits(currentToken[0],2):
                        cronvals[2]=currentToken[0]