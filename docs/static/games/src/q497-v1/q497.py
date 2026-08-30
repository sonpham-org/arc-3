"""q497 Spectrum Dependency -- build shared prism prerequisites while transferring one relation between representations."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GALLERY,PRISM,PERMIT,BUILT,FRAME,RELATION,BAD=12,10,15,14,11,9,13,8
LEVELS=[
 {"name":"First Pane","deps":(((),(0,),0),),"order":(0,)},{"name":"Shared Spectrum","deps":(((),(1,),1),((0,),(0,2),0)),"order":(0,1)},
 {"name":"Branching Prism","deps":(((),(2,),0),((0,),(1,),1),((0,1),(0,2),0)),"order":(0,1,2)},
 {"name":"Nested Relation","deps":(((),(0,2),1),((0,),(1,),0),((1,),(2,),1),((0,2),(0,1),0)),"order":(0,1,2,3)},
 {"name":"Transferred Graph","deps":(((),(1,2),0),((0,),(0,),1),((0,),(2,),0),((1,2),(0,1),1)),"order":(0,2,1,3)},
 {"name":"Spectrum Dependency","deps":(((),(0,1),1),((0,),(2,),0),((0,),(0,2),1),((1,2),(1,),0),((2,3),(0,1,2),1)),"order":(0,2,1,3,4)}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=GALLERY
  for i in range(len(LEVELS[g.level_index]["deps"])):
   x=7+i*10;f[11+i*6:16+i*6,x:x+8]=BUILT if i in g.built else PRISM
  for i,v in enumerate(sorted(g.permits)):f[44+i*4:47+i*4,8:8+v*13]=PERMIT
  f[53:57,8:29 if g.frame else 16]=FRAME;f[58:61,8:8+g.frame*20]=RELATION
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q497(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.cursor=self.frame=0;self.built=set();self.permits=set();self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q497",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.cursor=self.frame=0;self.built=set();self.permits=set();self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index];n=len(x["deps"])
  if a==0:self.complete_action();return
  if a in (1,2,3):self.permits.add((a-1+len(self.built)+self.frame)%3)
  elif a==5:self.cursor=(self.cursor+1)%n;self.permits.clear()
  elif a==6:self.frame^=1
  elif a==4:
   parents,need,want=x["deps"][self.cursor]
   if set(parents).issubset(self.built) and self.permits==set(need) and self.frame==want:
    self.built.add(self.cursor);self.permits.clear();self.frame^=self.cursor%2
    if len(self.built)==n:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
