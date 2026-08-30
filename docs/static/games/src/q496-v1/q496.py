"""q496 Crossing Dependency -- build shared ferry prerequisites from alternating controller evidence."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,RIVER,DOCK,PERMIT,BUILT,CONTROL,MARK,BAD=12,9,11,15,14,10,13,8
LEVELS=[
 {"name":"First Dock","deps":(((),(0,)),),"order":(0,)},{"name":"Shared Ferry","deps":(((),(1,)),((0,),(0,2))),"order":(0,1)},
 {"name":"Branching Crossing","deps":(((),(2,)),((0,),(1,)),((0,1),(0,2))),"order":(0,1,2)},
 {"name":"Nested Capacity","deps":(((),(0,2)),((0,),(1,)),((1,),(2,)),((0,2),(0,1))),"order":(0,1,2,3)},
 {"name":"Disjoint Views","deps":(((),(1,2)),((0,),(0,)),((0,),(2,)),((1,2),(0,1))),"order":(0,2,1,3)},
 {"name":"Crossing Dependency","deps":(((),(0,1)),((0,),(2,)),((0,),(0,2)),((1,2),(1,)),((2,3),(0,1,2))),"order":(0,2,1,3,4)}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=RIVER
  for i in range(len(LEVELS[g.level_index]["deps"])):
   x=7+i*10;f[11+i*6:16+i*6,x:x+8]=BUILT if i in g.built else DOCK
  for i,v in enumerate(sorted(g.permits)):f[44+i*4:47+i*4,8:8+v*13]=PERMIT
  f[53:57,8+g.controller*31:25+g.controller*31]=CONTROL;f[58:61,8:8+g.seen*12]=MARK
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q496(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.cursor=self.controller=self.seen=0;self.built=set();self.permits=set();self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q496",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.cursor=self.controller=self.seen=0;self.built=set();self.permits=set();self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index];n=len(x["deps"])
  if a==0:self.complete_action();return
  if a in (1,2,3):self.permits.add((a-1+len(self.built))%3);self.seen|=1<<self.controller
  elif a==5:self.cursor=(self.cursor+1)%n;self.permits.clear()
  elif a==6:self.controller^=1
  elif a==4:
   parents,need=x["deps"][self.cursor]
   if set(parents).issubset(self.built) and self.permits==set(need) and self.seen==3:
    self.built.add(self.cursor);self.permits.clear()
    if len(self.built)==n:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
