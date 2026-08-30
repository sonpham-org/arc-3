"""q204 Honeycomb Veil -- observation schedules coupled to local and outer clocks."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HIVE,CELL,NECTAR,SEEN,HIDDEN,OUTER,BAD=4,11,9,14,15,12,6,8
LEVELS=[{"name":n,"size":s,"cycle":c,"plan":p} for n,s,c,p in [("Hidden Courier",4,2,[2,1,2]),("Local Scent",5,3,[2,2,1,2]),("Outer Scent",6,2,[1,2,1,2,2]),("Coupled Cells",7,4,[2,1,2,1,2,2]),("Attention Cycle",8,3,[1,2,2,1,2,1,2]),("Honeycomb Veil",9,5,[2,1,2,2,1,2,1,2])]]
def advance(s,z,n,cycle):
 vals,focus,local,outer=s;v=list(vals)
 if z==1:focus=1-focus
 else:j=1-focus;v[j]=(v[j]+1+outer)%n
 local+=1
 if local==cycle:local=0;outer=(outer+1)%n
 return tuple(v),focus,local,outer
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=HIVE
  for i,v in enumerate(g.vals):x=9+i*32;f[15:29,x:x+14]=SEEN if i==g.focus else HIDDEN;f[32:36,x:x+v*2]=NECTAR
  f[43:47,8:8+g.local*9]=CELL;f[51:55,8:8+g.outer*5]=OUTER
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q204(ARCBaseGame):
 def __init__(self):self.display=D(self);self.vals=(0,1);self.focus=self.local=self.outer=0;self.target=None;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q204",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.vals=(0,1);self.focus=self.local=self.outer=0;s=(self.vals,0,0,0)
  for z in x["plan"]:s=advance(s,z,x["size"],x["cycle"])
  self.target=s;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2):self.vals,self.focus,self.local,self.outer=advance((self.vals,self.focus,self.local,self.outer),z,x["size"],x["cycle"])
  elif z==6:
   if (self.vals,self.focus,self.local,self.outer)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
