"""q401 Pollen Delegation -- integrate destructive local projections across a visible rule change."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,BLOOM,POLLEN,RELAY,WEAR,RULE,BAD=7,10,12,15,14,11,9,8
LEVELS=[
 {"name":"First Kite","clues":(1,2),"flow":(1,2,3),"boundary":2,"rule":1},{"name":"Complement Wind","clues":(2,3),"flow":(2,1,4),"boundary":2,"rule":2},
 {"name":"Vanishing Pollen","clues":(3,1),"flow":(1,3,1,2,4),"boundary":3,"rule":3},{"name":"Shared Meadow","clues":(1,3),"flow":(2,4,2,1,3),"boundary":3,"rule":0},
 {"name":"Wear Front","clues":(2,2),"flow":(1,2,3,1,4),"boundary":4,"rule":2},{"name":"Pollen Delegation","clues":(3,3),"flow":(2,1,4,2,3,1,4),"boundary":5,"rule":1}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=MEADOW
  f[12:23,8:24]=POLLEN if g.mem[0] else BLOOM;f[12:23,40:56]=POLLEN if g.mem[1] else BLOOM
  for i,v in enumerate(g.shared[-4:]):f[31+i*4:34+i*4,8:8+v*11]=RELAY
  f[49:52,8:8+min(g.wear,6)*7]=WEAR;f[54:58,8:8+g.candidate*11]=RULE
  if g.wear>=x["boundary"]:f[7:10,8:56]=WEAR
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q401(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mem=[0,0];self.seen=self.candidate=self.wear=0;self.shared=[];self.history=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q401",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mem=[0,0];self.seen=self.candidate=self.wear=0;self.shared=[];self.history=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:self.mem[0]=x["clues"][0];self.seen|=1;self.history.append(a);self.wear+=1
  elif a==2:self.mem[1]=x["clues"][1];self.seen|=2;self.history.append(a);self.wear+=1
  elif a==3:
   if self.mem[0]:self.shared.append((self.mem[0]+self.mem[1]+(self.wear>=x["boundary"]))%4);self.mem[0]=0;self.history.append(a);self.wear+=1
   else:self.bad=True;self.lose()
  elif a==4:
   if self.mem[1]:self.shared.append((2*self.mem[0]+self.mem[1]+2*(self.wear>=x["boundary"]))%4);self.mem[1]=0;self.history.append(a);self.wear+=1
   else:self.bad=True;self.lose()
  elif a==5:self.candidate=(self.candidate+1)%4
  elif a==6:
   if tuple(self.history)==x["flow"] and self.seen==3 and self.wear>=x["boundary"] and self.candidate==x["rule"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
