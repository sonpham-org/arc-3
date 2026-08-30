"""q394 Hive Courier -- merge private dance memories through ordered deposits."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HIVE,BEE,DANCE,DEPOSIT,CODE,BAD=7,11,12,15,14,10,8
LEVELS=[
 {"name":"First Dance","clues":(1,2),"flow":(1,2,3),"target":1},
 {"name":"Return Flight","clues":(2,3),"flow":(2,1,4),"target":2},
 {"name":"Split Nectar","clues":(3,1),"flow":(1,3,2,4),"target":3},
 {"name":"Shared Comb","clues":(1,3),"flow":(2,4,1,3),"target":0},
 {"name":"Crossed Waggle","clues":(2,2),"flow":(1,2,3,4,3),"target":2},
 {"name":"Hive Courier","clues":(3,3),"flow":(2,1,4,3,4,3),"target":1}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=HIVE;f[11:25,7:25]=BEE;f[11:25,39:57]=BEE
  f[15:21,12:20]=DANCE if g.seen&1 else HIVE;f[15:21,44:52]=DANCE if g.seen&2 else HIVE
  for i,v in enumerate(g.comb[-4:]):f[31+i*5:35+i*5,8:8+v*10]=DEPOSIT
  f[53:57,8:8+g.candidate*11]=CODE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q394(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mem=[0,0];self.seen=self.candidate=0;self.comb=[];self.history=[];self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q394",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mem=[0,0];self.seen=self.candidate=0;self.comb=[];self.history=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:self.mem[0]=x["clues"][0];self.seen|=1;self.history.append(a)
  elif a==2:self.mem[1]=x["clues"][1];self.seen|=2;self.history.append(a)
  elif a==3:self.comb.append((self.mem[0]+2*self.mem[1]+len(self.comb))%4);self.history.append(a)
  elif a==4:self.comb.append((2*self.mem[0]+self.mem[1]+len(self.comb))%4);self.history.append(a)
  elif a==5:self.candidate=(self.candidate+1)%4
  elif a==6:
   if tuple(self.history)==x["flow"] and self.seen==3 and self.candidate==x["target"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
