"""q048 Reveal Paint -- permanently expose a minimal spatial evidence set."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WALL,HIDDEN,PAINT,YES,NO,SHAPE,CURSOR,BAD=6,1,3,15,14,8,10,11,13
LEVELS=[
 {"name":"One Painted Cell","candidates":[0,1],"target":1,"cells":2,"budget":1},
 {"name":"Choose Location","candidates":[1,2,3],"target":1,"cells":3,"budget":1},
 {"name":"Boundary Pair","candidates":[0,3,5,6],"target":2,"cells":3,"budget":2},
 {"name":"Permanent Mark","candidates":[0,1,2,4,7],"target":4,"cells":3,"budget":2},
 {"name":"Spatial Allocation","candidates":[1,2,4,8,11,13],"target":5,"cells":4,"budget":2},
 {"name":"Reveal Paint","candidates":[0,3,5,6,9,10,12,15],"target":6,"cells":4,"budget":3}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,4:60]=WALL
  for i in range(g.cells):
   x=9+(i%3)*16;y=13+(i//3)*16;f[y:y+11,x:x+11]=YES if i in g.painted and g.candidates[g.target]&(1<<i) else NO if i in g.painted else HIDDEN;f[y-4:y-1,x:x+11]=CURSOR if i==g.cell else WALL
  for i in range(len(g.candidates)):x=7+i*7;f[44:50,x:x+5]=SHAPE;f[52:55,x:x+5]=CURSOR if i==g.hyp else WALL
  f[3:6,7:7+g.paint*7]=PAINT
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q048(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.candidates=[];self.target=self.cells=self.cell=self.hyp=self.paint=0;self.painted=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q048",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.candidates=list(s["candidates"]);self.target=s["target"];self.cells=s["cells"];self.paint=s["budget"];self.cell=self.hyp=0;self.painted=set();self.failed=False
 def identified(self):
  t=self.candidates[self.target];return all(i==self.target or any(((t>>b)&1)!=((v>>b)&1) for b in self.painted) for i,v in enumerate(self.candidates))
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.cell=(self.cell-1)%self.cells
  elif z==2:self.cell=(self.cell+1)%self.cells
  elif z==3:self.hyp=(self.hyp-1)%len(self.candidates)
  elif z==4:self.hyp=(self.hyp+1)%len(self.candidates)
  elif z==5:
   if self.cell not in self.painted and self.paint:self.painted.add(self.cell);self.paint-=1
   else:self.failed=True;self.lose()
  elif z==6:
   if self.hyp==self.target and self.identified():self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
