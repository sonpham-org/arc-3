"""q403 Impeller Delegation -- alternate destructive blade relays without paying for redundant samples."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TURBINE,BLADE,WAKE,RELAY,CONTROL,COST,BAD=7,6,15,12,14,10,13,8
LEVELS=[
 {"name":"First Relay","clues":(1,2),"flow":(1,2,3,4),"claim":1},{"name":"Alternating Wake","clues":(2,3),"flow":(2,1,4,3),"claim":2},
 {"name":"Vanishing Blade","clues":(3,1),"flow":(1,3,1,2,4,3),"claim":3},{"name":"Cost Boundary","clues":(1,3),"flow":(2,4,2,1,3,4),"claim":0},
 {"name":"Shared Turbine","clues":(2,2),"flow":(1,2,3,1,4,3),"claim":2},{"name":"Impeller Delegation","clues":(3,3),"flow":(2,1,4,2,3,1,4,3),"claim":1}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=TURBINE;f[12:23,8:24]=BLADE if g.mem[0] else WAKE;f[12:23,40:56]=BLADE if g.mem[1] else WAKE
  for i,v in enumerate(g.shared[-5:]):f[30+i*4:33+i*4,8:8+v*11]=RELAY
  f[50:54,8+g.controller*31:25+g.controller*31]=CONTROL;f[55:59,8:8+g.samples*5]=COST
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q403(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mem=[0,0];self.controller=self.samples=self.claim=0;self.shared=[];self.history=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q403",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mem=[0,0];self.controller=self.samples=self.claim=0;self.shared=[];self.history=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2):self.mem[a-1]=x["clues"][a-1];self.samples+=1;self.history.append(a)
  elif a in (3,4):
   i=a-3
   if self.mem[i]:self.shared.append((self.mem[i]+self.mem[1-i]+self.controller)%4);self.mem[i]=0;self.controller^=1;self.history.append(a)
   else:self.bad=True;self.lose()
  elif a==5:self.claim=(self.claim+1)%4
  elif a==6:
   optimum=sum(a in (1,2) for a in x["flow"])
   if tuple(self.history)==x["flow"] and self.samples==optimum and self.claim==x["claim"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
