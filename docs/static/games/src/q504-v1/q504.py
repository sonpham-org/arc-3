"""q504 Honeycomb Frame -- moving local controls across nested scent clocks."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HIVE,CELL,NECTAR,FRAME,LOCAL,OUTER,BAD=4,11,9,14,15,12,6,8
LEVELS=[{"name":n,"size":s,"cycle":c,"plan":p} for n,s,c,p in [
 ("Local Cell",6,2,[2,1,2]),("Outer Scent",7,3,[3,2,1,2]),("Edge Exchange",8,3,[2,3,1,2,1]),
 ("Nested Clocks",9,4,[1,3,2,2,1,3]),("Global Alignment",10,4,[2,1,3,2,1,2,3]),("Honeycomb Frame",11,5,[3,2,1,3,2,2,1,3])]]
def advance(s,z,n,cycle):
 pos,rot,local,outer=s
 if z==3:rot=(rot+1)%4
 else:pos=(pos+(-1 if z==1 else 1)*(-1 if rot%2 else 1)+outer)%n
 local+=1
 if local==cycle:local=0;outer=(outer+1)%n
 return pos,rot,local,outer
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[6:58,4:60]=HIVE
  for i in range(g.n):x=7+i*(50//g.n);f[20:34,x:x+5]=CELL
  x=7+g.pos*(50//g.n);f[13:18,x:x+6]=NECTAR;f[39:43,8:8+g.rot*10]=FRAME;f[47:50,8:8+g.local*8]=LOCAL;f[53:56,8:8+g.outer*4]=OUTER
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q504(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.n=1;self.pos=self.rot=self.local=self.outer=0;self.target=None;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q504",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.n=x["size"];self.pos=self.rot=self.local=self.outer=0;s=(0,0,0,0)
  for z in x["plan"]:s=advance(s,z,self.n,x["cycle"])
  self.target=s;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z in (1,2,3):self.pos,self.rot,self.local,self.outer=advance((self.pos,self.rot,self.local,self.outer),z,self.n,x["cycle"])
  elif z==6:
   if (self.pos,self.rot,self.local,self.outer)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
