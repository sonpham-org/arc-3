"""q211 Periscope Current -- navigate physical space through a rotatable view frame."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SEA,GRID,DIVER,GOAL,VIEW,BAD=0,10,1,12,14,15,8
LEVELS=[
 {"name":"First Bearing","size":6,"plan":(2,2,3)},
 {"name":"Turned Scope","size":7,"plan":(2,5,2,3)},
 {"name":"Counter Bearing","size":8,"plan":(1,5,2,2,3)},
 {"name":"Frame Crossing","size":9,"plan":(2,3,5,1,2,3)},
 {"name":"Current Map","size":10,"plan":(2,5,3,3,5,1,2)},
 {"name":"Periscope Current","size":11,"plan":(2,3,5,2,2,5,1,3)}]
VECTORS=((0,-1),(1,0),(0,1),(-1,0))
def advance(state,a,size):
 pos,view=state;x,y=pos
 if a==5:view=(view+1)%4
 else:
  d=(a-1+view)%4;dx,dy=VECTORS[d];x=max(0,min(size-1,x+dx));y=max(0,min(size-1,y+dy))
 return (x,y),view
def target(x):
 s=((1,1),0)
 for a in x["plan"]:s=advance(s,a,x["size"])
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=SEA;cell=max(3,46//x["size"])
  for k in range(x["size"]+1):f[8+k*cell:9+k*cell,7:7+x["size"]*cell]=GRID;f[8:8+x["size"]*cell,7+k*cell:8+k*cell]=GRID
  tx,ty=g.target[0];px,py=g.pos;f[9+ty*cell:8+(ty+1)*cell,8+tx*cell:7+(tx+1)*cell]=GOAL;f[9+py*cell:8+(py+1)*cell,8+px*cell:7+(px+1)*cell]=DIVER
  f[53:57,8:8+g.view*11]=VIEW
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q211(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.pos=(1,1);self.view=0;self.target=((1,1),0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q211",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.pos=(1,1);self.view=0;self.target=target(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.view=advance((self.pos,self.view),a,x["size"])
  elif a==6:
   if (self.pos,self.view)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
