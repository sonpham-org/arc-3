"""q450 Spore Lineage -- preserve ancestry through appearance exchange and sparse clocks."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GREENHOUSE,SPORE,TRAIL,CLOCKA,CLOCKB,CURSOR,BAD=10,2,13,15,14,12,6,8
LEVELS=[
 {"name":"Causal Trail","ops":[1,2],"mods":[3,4],"ancestor":0},
 {"name":"Appearance Exchange","ops":[2,1,1],"mods":[4,5],"ancestor":1},
 {"name":"Split and Merge","ops":[1,2,1,2],"mods":[5,6],"ancestor":2},
 {"name":"Unequal Schedules","ops":[2,2,1,2,1],"mods":[6,7],"ancestor":0},
 {"name":"Sparse Shared Event","ops":[1,1,2,1,2,2],"mods":[7,8],"ancestor":2},
 {"name":"Spore Lineage","ops":[2,1,2,2,1,1,2],"mods":[8,9],"ancestor":1}]
def transform(perm,z):
 p=list(perm)
 if z==1:p=p[1:]+p[:1]
 else:p[0],p[-1]=p[-1],p[0]
 return tuple(p)
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[5:59,5:59]=GREENHOUSE
  for i,v in enumerate(g.perm):x=9+i*17;f[18:31,x:x+11]=SPORE;f[32:35,x:x+3+v*3]=TRAIL
  f[42:46,8:8+g.phase[0]*6]=CLOCKA;f[48:52,8:8+g.phase[1]*5]=CLOCKB;f[54:58,9+g.cursor*17:20+g.cursor*17]=CURSOR
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q450(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.perm=(0,1,2);self.phase=[0,0];self.cursor=self.target=0;self.progress=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q450",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];p=(0,1,2)
  for z in x["ops"]:p=transform(p,z)
  self.target=p.index(x["ancestor"]);self.perm=(0,1,2);self.phase=[0,0];self.cursor=self.progress=0;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2) and self.progress<len(x["ops"]) and z==x["ops"][self.progress]:self.perm=transform(self.perm,z);self.phase=[(self.phase[i]+1)%x["mods"][i] for i in range(2)];self.progress+=1
  elif z==3 and self.progress==len(x["ops"]):self.cursor=(self.cursor+1)%3
  elif z==6:
   if self.progress==len(x["ops"]) and self.cursor==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
