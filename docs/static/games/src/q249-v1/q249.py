"""q249 Reedbed Pact -- infer a convention while every offer changes the constructed route."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MARSH,REED,OFFER,LINK,ROUTE,ROLE,BAD=1,14,11,15,12,10,13,8
LEVELS=[
 {"name":"First Offer","role":0,"plan":(1,)},{"name":"Rewired Reply","role":1,"plan":(2,1)},
 {"name":"Reciprocal Route","role":2,"plan":(3,2,1)},{"name":"Constructed Pact","role":1,"plan":(1,3,2,1)},
 {"name":"Obstructed Convention","role":0,"plan":(2,1,3,2,1)},{"name":"Reedbed Pact","role":2,"plan":(3,1,2,3,1,2)}]
def simulate(x):
 meter=link=0
 for a in x["plan"]:meter=(meter+a+x["role"]*(a+1)+link)%7;link=(link+a+meter)%3
 return meter,link
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=MARSH
  for i in range(3):f[11:27,9+i*17:20+i*17]=REED
  f[34:39,8:8+g.meter*7]=OFFER;f[43:48,8:8+g.link*14]=LINK;f[50:54,8:29 if g.installed else 16]=ROUTE;f[55:59,8:8+g.role*14]=ROLE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q249(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.meter=self.link=self.role=0;self.installed=False;self.history=[];self.target=(0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q249",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.meter=self.link=self.role=0;self.installed=False;self.history=[];self.target=simulate(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.meter=(self.meter+a+x["role"]*(a+1)+self.link)%7;self.link=(self.link+a+self.meter)%3;self.history.append(a)
  elif a==4:self.installed=True
  elif a==5:self.role=(self.role+1)%3
  elif a==6:
   if tuple(self.history)==x["plan"] and (self.meter,self.link)==self.target and self.installed and self.role==x["role"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
