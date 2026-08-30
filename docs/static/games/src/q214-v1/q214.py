"""q214 Gravity Lantern -- navigate rotated controls with automatic gravity drift."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SKY,GRID,LANTERN,GOAL,FRAME,GRAVITY,BAD=0,10,1,12,14,15,11,8
LEVELS=[
 {"name":"First Fall","size":7,"plan":(2,2,1)},{"name":"Turned Gravity","size":8,"plan":(2,5,2,1)},
 {"name":"Counter Drift","size":9,"plan":(4,5,2,2,1)},{"name":"Frame Fall","size":10,"plan":(2,1,5,4,2,1)},
 {"name":"Gravity Map","size":11,"plan":(2,5,1,1,5,4,2)},{"name":"Gravity Lantern","size":12,"plan":(2,1,5,2,2,5,4,1)}]
VECTORS=((0,-1),(1,0),(0,1),(-1,0))
def clamp(v,size):return max(0,min(size-1,v))
def advance(state,a,size):
 pos,view,gravity=state;x,y=pos
 if a==5:view=(view+1)%4;gravity=(gravity+1)%4
 else:
  dx,dy=VECTORS[(a-1+view)%4];x=clamp(x+dx,size);y=clamp(y+dy,size);gx,gy=VECTORS[gravity];x=clamp(x+gx,size);y=clamp(y+gy,size)
 return (x,y),view,gravity
def target(x):
 s=((x["size"]//2,x["size"]//2),0,2)
 for a in x["plan"]:s=advance(s,a,x["size"])
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=SKY;cell=max(3,44//x["size"])
  for k in range(x["size"]+1):f[8+k*cell:9+k*cell,7:7+x["size"]*cell]=GRID;f[8:8+x["size"]*cell,7+k*cell:8+k*cell]=GRID
  tx,ty=g.target[0];px,py=g.pos;f[9+ty*cell:8+(ty+1)*cell,8+tx*cell:7+(tx+1)*cell]=GOAL;f[9+py*cell:8+(py+1)*cell,8+px*cell:7+(px+1)*cell]=LANTERN
  f[53:56,8:8+g.view*11]=FRAME;f[57:60,8:8+g.gravity*11]=GRAVITY
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q214(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.pos=(3,3);self.view=0;self.gravity=2;self.target=((3,3),0,2);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q214",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.pos=(x["size"]//2,x["size"]//2);self.view=0;self.gravity=2;self.target=target(x);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.view,self.gravity=advance((self.pos,self.view,self.gravity),a,x["size"])
  elif a==6:
   if (self.pos,self.view,self.gravity)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
