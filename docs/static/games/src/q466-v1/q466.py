"""q466 Crossing Lineage -- integrate disjoint controller marks while tracking passenger ancestors."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,RIVER,PASSENGER,DOCK,ANCESTOR,CONTROL,CLAIM,BAD=11,9,15,12,14,10,13,8
LEVELS=[
 {"name":"First Crossing","ancestor":0,"ops":(1,6,2)},{"name":"Split Dock","ancestor":1,"ops":(2,6,1,3)},
 {"name":"Merged Ferry","ancestor":2,"ops":(3,1,6,2)},{"name":"Disjoint Views","ancestor":3,"ops":(1,3,6,2,3)},
 {"name":"Capacity Lineage","ancestor":1,"ops":(2,1,6,3,2,1)},{"name":"Crossing Lineage","ancestor":2,"ops":(3,1,2,6,3,1,2)}]
def transform(o,a):
 o=[set(v) for v in o]
 if a==1:o[0],o[-1]=o[-1],o[0]
 elif a==2:o[1]|=o[0];o=o[1:]+o[:1]
 elif a==3:o=o[-1:]+o[:-1]
 return tuple(frozenset(v) for v in o)
def result(x):
 o=tuple(frozenset((i,)) for i in range(4));controller=seen=0
 for a in x["ops"]:
  if a in (1,2,3):o=transform(o,a);seen|=1<<controller
  else:controller^=1
 return o,min(i for i,v in enumerate(o) if x["ancestor"] in v),seen,controller
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=RIVER
  for i,lineage in enumerate(g.lineages):
   x=7+i*14;f[12:27,x:x+10]=PASSENGER
   for j,_ in enumerate(sorted(lineage)):f[29+j*3:31+j*3,x:x+10]=ANCESTOR
  f[43:47,8+g.controller*31:25+g.controller*31]=CONTROL;f[49:53,8:8+g.seen*12]=DOCK;f[55:59,8:8+g.claim*12]=CLAIM
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q466(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.lineages=tuple(frozenset((i,)) for i in range(4));self.controller=self.seen=self.claim=0;self.history=[];self.target=(self.lineages,0,0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q466",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.lineages=tuple(frozenset((i,)) for i in range(4));self.controller=self.seen=self.claim=0;self.history=[];self.target=result(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.lineages=transform(self.lineages,a);self.seen|=1<<self.controller;self.history.append(a)
  elif a==6:self.controller^=1;self.history.append(a)
  elif a==5:self.claim=(self.claim+1)%4
  elif a==4:
   if tuple(self.history)==x["ops"] and self.lineages==self.target[0] and self.claim==self.target[1] and self.seen==3:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
