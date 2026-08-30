"""q279 Reedbed Probe -- diagnose hidden salinity causes while every repair rewires connectivity."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MARSH,REED,PULSE,LINK,REPAIR,MODEL,BAD=2,14,11,15,12,10,9,8
LEVELS=[
 {"name":"First Probe","model":0,"plan":(1,4)},{"name":"Shared Front","model":1,"plan":(2,4,1)},
 {"name":"Rewired Cause","model":2,"plan":(3,1,4,2)},{"name":"Topology Repair","model":3,"plan":(1,2,4,3,1)},
 {"name":"Salinity Fork","model":4,"plan":(2,3,1,4,2,1)},{"name":"Reedbed Probe","model":5,"plan":(3,1,4,2,3,4,1)}]
def advance(s,a,model):
 signal,link=s
 if a in (1,2,3):signal=(signal+a+model+link)%5;link=(link+a+signal)%3
 else:link=(link+model+1)%3;signal=(signal+2*link)%5
 return signal,link
def target(x):
 s=(0,0)
 for a in x["plan"]:s=advance(s,a,x["model"])
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=MARSH
  for i in range(3):f[11:27,9+i*17:20+i*17]=REED
  f[34:39,8:8+g.signal*9]=PULSE;f[43:48,8:8+g.link*14]=LINK;f[51:55,8:29 if 4 in g.history else 16]=REPAIR;f[56:60,8:8+g.candidate*8]=MODEL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q279(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.signal=self.link=self.candidate=0;self.history=[];self.target=(0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q279",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.signal=self.link=self.candidate=0;self.history=[];self.target=target(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.signal,self.link=advance((self.signal,self.link),a,x["model"]);self.history.append(a)
  elif a==5:self.candidate=(self.candidate+1)%6
  elif a==6:
   if tuple(self.history)==x["plan"] and (self.signal,self.link)==self.target and self.candidate==x["model"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
