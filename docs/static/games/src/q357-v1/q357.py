"""q357 Canopy Rig -- assemble capacity-bounded reusable orchard modules."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,BRANCH,GLIDER,STORE,MODULE,EFFECT,BAD=7,11,13,14,12,15,10,8
LEVELS=[
 {"name":"Redirector","capacity":2,"modules":[[1,2]]},
 {"name":"Joined Branch","capacity":2,"modules":[[2,3],[1,2]]},
 {"name":"Support Store","capacity":3,"modules":[[1,3,2],[2,1]]},
 {"name":"Seasonal Device","capacity":3,"modules":[[3,2],[1,3],[2,1]]},
 {"name":"Two Effects","capacity":3,"modules":[[1,2,3],[3,1,2],[2,3]]},
 {"name":"Canopy Rig","capacity":3,"modules":[[2,1,3],[1,3],[3,2,1],[2,3]]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;l=LEVELS[g.level_index];f[:,:]=BG;f[5:59,5:59]=ORCHARD;f[11:16,8:56]=BRANCH
  for i,z in enumerate(g.store):f[24:32,9+i*14:19+i*14]=STORE;f[26:30,11+i*14:11+i*14+z*2]=GLIDER
  for i in range(len(l["modules"])):f[43:49,9+i*11:17+i*11]=EFFECT if i<g.progress else MODULE
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q357(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.store=[];self.progress=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q357",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,6])
 def on_set_level(self,l):self.store=[];self.progress=0;self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  l=LEVELS[self.level_index]
  if z in (1,2,3) and len(self.store)<l["capacity"]:self.store.append(z)
  elif z==4:
   if self.progress<len(l["modules"]) and self.store==l["modules"][self.progress]:self.progress+=1;self.store=[]
   else:self.fail()
  elif z==6:
   if self.progress==len(l["modules"]) and not self.store:self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()
