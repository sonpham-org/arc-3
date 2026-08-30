"""q780 Spore Rhythm -- align two event clocks through interruptible macro-time."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GREENHOUSE,SPORE,CLOCKA,CLOCKB,MACRO,TARGET,BAD=10,2,13,14,12,15,11,8
LEVELS=[
 {"name":"Shared Pulse","mods":[4,5],"target":[2,3],"chunks":1},
 {"name":"Unequal Seasons","mods":[5,7],"target":[4,1],"chunks":1},
 {"name":"Macro Burst","mods":[6,7],"target":[1,5],"chunks":2},
 {"name":"Interrupted Growth","mods":[7,8],"target":[6,2],"chunks":1},
 {"name":"Nested Rhythm","mods":[8,9],"target":[3,7],"chunks":2},
 {"name":"Spore Rhythm","mods":[9,11],"target":[8,6],"chunks":3}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;l=LEVELS[g.level_index];f[:,:]=BG;f[5:59,5:59]=GREENHOUSE
  for i,(p,m,col) in enumerate(zip(g.phase,l["mods"],(CLOCKA,CLOCKB))):
   y=16+i*22;f[y:y+8,9:55]=SPORE;f[y:y+8,9:9+int(46*p/max(1,m-1))]=col;tx=9+int(46*l["target"][i]/max(1,m-1));f[y-2:y+10,tx:tx+2]=TARGET
  f[55:58,8:8+g.chunks*8]=MACRO
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q780(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.phase=[0,0];self.chunks=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q780",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):self.phase=[0,0];self.chunks=0;self.bad=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  l=LEVELS[self.level_index]
  if z==3:self.phase[0]=(self.phase[0]+1)%l["mods"][0]
  elif z==4:self.phase[1]=(self.phase[1]+1)%l["mods"][1]
  elif z==5:self.phase=[(self.phase[i]+3)%l["mods"][i] for i in range(2)];self.chunks+=1
  elif z==6:
   if self.phase==l["target"] and self.chunks>=l["chunks"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
