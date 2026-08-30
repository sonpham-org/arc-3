"""q400 Ant Relay -- move clues through destructive, direction-specific colony memories."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,NEST,TUNNEL,SCENT,RELAY,CODE,BAD=7,9,11,14,15,10,8
LEVELS=[
 {"name":"First Trail","clues":(1,2),"flow":(1,2,3),"target":1},{"name":"Return Trail","clues":(2,3),"flow":(2,1,4),"target":2},
 {"name":"Vanishing Scent","clues":(3,1),"flow":(1,3,1,2,4),"target":3},{"name":"Shared Colony","clues":(1,3),"flow":(2,4,2,1,3),"target":0},
 {"name":"Crossed Tunnel","clues":(2,2),"flow":(1,2,3,1,4),"target":2},{"name":"Ant Relay","clues":(3,3),"flow":(2,1,4,2,3,1,4),"target":1}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=NEST;f[27:33,8:56]=TUNNEL
  f[12:22,9:23]=SCENT if g.mem[0] else NEST;f[12:22,41:55]=SCENT if g.mem[1] else NEST
  for i,v in enumerate(g.shared[-4:]):f[35+i*4:38+i*4,8:8+v*11]=RELAY
  f[53:57,8:8+g.candidate*11]=CODE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q400(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mem=[0,0];self.seen=self.candidate=0;self.shared=[];self.history=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q400",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mem=[0,0];self.seen=self.candidate=0;self.shared=[];self.history=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:self.mem[0]=x["clues"][0];self.seen|=1;self.history.append(a)
  elif a==2:self.mem[1]=x["clues"][1];self.seen|=2;self.history.append(a)
  elif a==3:
   if self.mem[0]:self.shared.append((self.mem[0]+2*self.mem[1]+len(self.shared))%4);self.mem[0]=0;self.history.append(a)
   else:self.bad=True;self.lose()
  elif a==4:
   if self.mem[1]:self.shared.append((2*self.mem[0]+self.mem[1]+len(self.shared))%4);self.mem[1]=0;self.history.append(a)
   else:self.bad=True;self.lose()
  elif a==5:self.candidate=(self.candidate+1)%4
  elif a==6:
   if tuple(self.history)==x["flow"] and self.seen==3 and self.candidate==x["target"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
