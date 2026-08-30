"""q146 Fork Seal -- committing to a branch permanently seals its sibling."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CAVE,FORK,OPEN,SEALED,GOAL,PREVIEW,BAD=14,1,3,10,8,12,15,6
LEVELS=[
 {"name":"One Irreversible Fork","path":[0,1]}, {"name":"Preview Downstream","path":[1,0,1]},
 {"name":"Compatibility Chain","path":[0,1,1,0]}, {"name":"Sibling Seal","path":[1,1,0,1,0]},
 {"name":"Long Consequence","path":[0,1,0,1,1,0]}, {"name":"Fork Seal","path":[1,0,1,1,0,1,0]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CAVE
  for i,b in enumerate(g.path):x=8+i*7;f[22:34,x:x+5]=OPEN if i<len(g.chosen) else FORK;f[37:43,x:x+5]=SEALED if i<len(g.chosen) else GOAL
  if g.preview:f[14:18,8:56]=PREVIEW
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q146(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.path=self.chosen=[];self.preview=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q146",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,5,6])
 def on_set_level(self,l):self.path=list(LEVELS[self.level_index]["path"]);self.chosen=[];self.preview=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2):self.chosen.append(z-1);self.preview=False
  elif z==5:self.preview=True
  elif z==6:
   if self.chosen==self.path:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
