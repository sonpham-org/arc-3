"""q494 Tower Dependency -- construct dependency floors with support permits remapped by progress."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SKY,FLOOR,PERMIT,BUILT,CURSOR,BAD=12,9,11,15,14,10,8
LEVELS=[
 {"name":"First Floor","deps":(((),(0,)),),"order":(0,)},{"name":"Anchored Floor","deps":(((),(1,)),((0,),(0,2))),"order":(0,1)},
 {"name":"Branching Tower","deps":(((),(2,)),((0,),(1,)),((0,1),(0,2))),"order":(0,1,2)},
 {"name":"Nested Tower","deps":(((),(0,2)),((0,),(1,)),((1,),(2,)),((0,2),(0,1))),"order":(0,1,2,3)},
 {"name":"Shifting Supports","deps":(((),(1,2)),((0,),(0,)),((0,),(2,)),((1,2),(0,1))),"order":(0,2,1,3)},
 {"name":"Tower Dependency","deps":(((),(0,1)),((0,),(2,)),((0,),(0,2)),((1,2),(1,)),((2,3),(0,1,2))),"order":(0,2,1,3,4)}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SKY
  for i in range(len(LEVELS[g.level_index]["deps"])):
   x=7+i*10;f[39-i*6:45-i*6,x:x+8]=BUILT if i in g.built else (CURSOR if i==g.cursor else FLOOR)
  for i,v in enumerate(sorted(g.permits)):f[48+i*4:51+i*4,8:8+v*13]=PERMIT
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q494(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.cursor=0;self.built=set();self.permits=set();self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q494",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.cursor=0;self.built=set();self.permits=set();self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index];n=len(x["deps"])
  if a==0:self.complete_action();return
  if a in (1,2,3):self.permits.add((a-1+len(self.built))%3)
  elif a==5:self.cursor=(self.cursor+1)%n;self.permits.clear()
  elif a==4:
   parents,need=x["deps"][self.cursor]
   if set(parents).issubset(self.built) and self.permits==set(need):self.built.add(self.cursor);self.permits.clear()
   else:self.bad=True;self.lose()
  elif a==6:
   if len(self.built)==n:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
