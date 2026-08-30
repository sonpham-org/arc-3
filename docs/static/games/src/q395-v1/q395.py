"""q395 Firefly Relay -- merge private flashes through ordered lantern deposits."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,FIREFLY,FLASH,LANTERN,CODE,BAD=7,14,11,15,12,10,8
LEVELS=[
 {"name":"First Flash","clues":(1,2),"flow":(1,2,3),"target":1},{"name":"Return Glow","clues":(2,3),"flow":(2,1,4),"target":2},
 {"name":"Split Meadow","clues":(3,1),"flow":(1,3,2,4),"target":3},{"name":"Shared Lantern","clues":(1,3),"flow":(2,4,1,3),"target":0},
 {"name":"Crossed Blink","clues":(2,2),"flow":(1,2,3,4,3),"target":2},{"name":"Firefly Relay","clues":(3,3),"flow":(2,1,4,3,4,3),"target":1}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=MEADOW;f[12:24,7:25]=FIREFLY;f[12:24,39:57]=FIREFLY
  f[15:21,12:20]=FLASH if g.seen&1 else MEADOW;f[15:21,44:52]=FLASH if g.seen&2 else MEADOW
  for i,v in enumerate(g.lantern[-4:]):f[31+i*5:35+i*5,8:8+v*10]=LANTERN
  f[53:57,8:8+g.candidate*11]=CODE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q395(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mem=[0,0];self.seen=self.candidate=0;self.lantern=[];self.history=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q395",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mem=[0,0];self.seen=self.candidate=0;self.lantern=[];self.history=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:self.mem[0]=x["clues"][0];self.seen|=1;self.history.append(a)
  elif a==2:self.mem[1]=x["clues"][1];self.seen|=2;self.history.append(a)
  elif a==3:self.lantern.append((self.mem[0]+2*self.mem[1]+len(self.lantern))%4);self.history.append(a)
  elif a==4:self.lantern.append((2*self.mem[0]+self.mem[1]+len(self.lantern))%4);self.history.append(a)
  elif a==5:self.candidate=(self.candidate+1)%4
  elif a==6:
   if tuple(self.history)==x["flow"] and self.seen==3 and self.candidate==x["target"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
