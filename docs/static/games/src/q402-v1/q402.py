"""q402 Semaphore Delegation -- alternate destructive partial relays before one irreversible policy."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CLIFF,FLAG,BEAM,RELAY,CONTROL,POLICY,BAD=7,12,15,14,11,10,9,8
LEVELS=[
 {"name":"First Signal","clues":(1,2),"flow":(1,2,3,4),"policy":1},{"name":"Alternating Beam","clues":(2,3),"flow":(2,1,4,3),"policy":2},
 {"name":"Vanishing Flag","clues":(3,1),"flow":(1,3,1,2,4,3),"policy":3},{"name":"Dual Test","clues":(1,3),"flow":(2,4,2,1,3,4),"policy":0},
 {"name":"Shared Yard","clues":(2,2),"flow":(1,2,3,1,4,3),"policy":2},{"name":"Semaphore Delegation","clues":(3,3),"flow":(2,1,4,2,3,1,4,3),"policy":1}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=CLIFF;f[12:23,8:24]=FLAG if g.mem[0] else BEAM;f[12:23,40:56]=FLAG if g.mem[1] else BEAM
  for i,v in enumerate(g.shared[-5:]):f[30+i*4:33+i*4,8:8+v*11]=RELAY
  f[50:54,8+g.controller*31:25+g.controller*31]=CONTROL;f[55:59,8:8+g.policy*11]=POLICY
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q402(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mem=[0,0];self.controller=self.evidence=self.policy=0;self.shared=[];self.history=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q402",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mem=[0,0];self.controller=self.evidence=self.policy=0;self.shared=[];self.history=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:self.mem[0]=x["clues"][0];self.history.append(a)
  elif a==2:self.mem[1]=x["clues"][1];self.history.append(a)
  elif a in (3,4):
   i=a-3
   if self.mem[i]:self.shared.append((self.mem[i]+self.mem[1-i]+self.controller)%4);self.mem[i]=0;self.evidence|=1<<self.controller;self.controller^=1;self.history.append(a)
   else:self.bad=True;self.lose()
  elif a==5:self.policy=(self.policy+1)%4
  elif a==6:
   if tuple(self.history)==x["flow"] and self.evidence==3 and self.policy==x["policy"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
