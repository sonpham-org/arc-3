"""q498 Escapement Dependency -- build nested gear prerequisites after selecting a discriminating fault."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TOWER,GEAR,PERMIT,BUILT,FAULT,CURSOR,BAD=12,3,15,14,11,10,9,8
LEVELS=[
 {"name":"First Gear","fault":0,"deps":(((),(0,)),),"order":(0,)},{"name":"Shared Weight","fault":1,"deps":(((),(1,)),((0,),(0,2))),"order":(0,1)},
 {"name":"Branching Clock","fault":2,"deps":(((),(2,)),((0,),(1,)),((0,1),(0,2))),"order":(0,1,2)},
 {"name":"Nested Fault","fault":1,"deps":(((),(0,2)),((0,),(1,)),((1,),(2,)),((0,2),(0,1))),"order":(0,1,2,3)},
 {"name":"Discriminating Probe","fault":2,"deps":(((),(1,2)),((0,),(0,)),((0,),(2,)),((1,2),(0,1))),"order":(0,2,1,3)},
 {"name":"Escapement Dependency","fault":1,"deps":(((),(0,1)),((0,),(2,)),((0,),(0,2)),((1,2),(1,)),((2,3),(0,1,2))),"order":(0,2,1,3,4)}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=TOWER
  for i in range(len(LEVELS[g.level_index]["deps"])):
   x=7+i*10;f[11+i*6:16+i*6,x:x+8]=BUILT if i in g.built else GEAR
  for i,v in enumerate(sorted(g.permits)):f[44+i*4:47+i*4,8:8+v*13]=PERMIT
  f[53:57,8:8+g.fault*14]=FAULT;f[58:61,8+g.cursor*8:15+g.cursor*8]=CURSOR
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q498(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.cursor=self.fault=0;self.built=set();self.permits=set();self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q498",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.cursor=self.fault=0;self.built=set();self.permits=set();self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index];n=len(x["deps"])
  if a==0:self.complete_action();return
  if a in (1,2,3):self.permits.add((a-1+len(self.built))%3)
  elif a==5:self.cursor=(self.cursor+1)%n;self.permits.clear()
  elif a==6:self.fault=(self.fault+1)%3
  elif a==4:
   parents,need=x["deps"][self.cursor]
   if set(parents).issubset(self.built) and self.permits==set(need) and self.fault==x["fault"]:
    self.built.add(self.cursor);self.permits.clear()
    if len(self.built)==n:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
