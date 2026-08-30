"""q396 Coral Signal -- coordinate destructive relays between partial reef observers."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REEF,POLYP,TONE,RELAY,CODE,BAD=7,10,12,15,14,11,8
LEVELS=[
 {"name":"First Pulse","clues":(1,2),"flow":(1,2,3),"target":1},{"name":"Return Current","clues":(2,3),"flow":(2,1,4),"target":2},
 {"name":"Destructive Relay","clues":(3,1),"flow":(1,3,1,2,4),"target":3},{"name":"Shared Reef","clues":(1,3),"flow":(2,4,2,1,3),"target":0},
 {"name":"Crossed Current","clues":(2,2),"flow":(1,2,3,1,4),"target":2},{"name":"Coral Signal","clues":(3,3),"flow":(2,1,4,2,3,1,4),"target":1}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=REEF;f[12:25,7:25]=POLYP;f[12:25,39:57]=POLYP
  f[15:21,12:20]=TONE if g.mem[0] else REEF;f[15:21,44:52]=TONE if g.mem[1] else REEF
  for i,v in enumerate(g.shared[-4:]):f[31+i*5:35+i*5,8:8+v*10]=RELAY
  f[53:57,8:8+g.candidate*11]=CODE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q396(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mem=[0,0];self.seen=self.candidate=0;self.shared=[];self.history=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q396",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mem=[0,0];self.seen=self.candidate=0;self.shared=[];self.history=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:self.mem[0]=x["clues"][0];self.seen|=1;self.history.append(a)
  elif a==2:self.mem[1]=x["clues"][1];self.seen|=2;self.history.append(a)
  elif a==3:
   if self.mem[0]:self.shared.append((2*self.mem[0]+self.mem[1])%4);self.mem[0]=0;self.history.append(a)
   else:self.bad=True;self.lose()
  elif a==4:
   if self.mem[1]:self.shared.append((self.mem[0]+2*self.mem[1])%4);self.mem[1]=0;self.history.append(a)
   else:self.bad=True;self.lose()
  elif a==5:self.candidate=(self.candidate+1)%4
  elif a==6:
   if tuple(self.history)==x["flow"] and self.seen==3 and self.candidate==x["target"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
