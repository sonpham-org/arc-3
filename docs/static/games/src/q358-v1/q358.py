"""q358 Breakwater Rig -- build a reusable harbor tool with a dormant first effect."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,CHANNEL,SKIFF,PART,MODULE,LATENT,BAD=8,10,14,12,15,13,6,3
LEVELS=[
 {"name":"Redirector","modules":[[1,2]],"latent":1},{"name":"Joined Channel","modules":[[2,3],[1,2]],"latent":2},
 {"name":"Support Span","modules":[[3,1],[2,3]],"latent":3},{"name":"Dormant Gate","modules":[[2,1,3],[1,2]],"latent":2},
 {"name":"Two Effects","modules":[[1,3,2],[3,1],[2,3]],"latent":1},{"name":"Breakwater Rig","modules":[[3,2,1],[1,2,3],[2,1]],"latent":3}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;l=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=HARBOR;f[13:18,8:56]=CHANNEL;f[21:31,9:21]=SKIFF
  for i,z in enumerate(g.store):f[34:42,8+i*13:18+i*13]=PART
  for i in range(len(l["modules"])):f[47:52,8+i*12:18+i*12]=MODULE if i>=g.progress else LATENT
  if g.first:f[54:58,45:45+g.first*4]=LATENT
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q358(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.store=[];self.progress=0;self.first=None;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q358",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,6])
 def on_set_level(self,l):self.store=[];self.progress=0;self.first=None;self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value;l=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2,3) and len(self.store)<3:
   self.store.append(z)
   if self.first is None:self.first=z
  elif z==4:
   if self.progress<len(l["modules"]) and self.store==l["modules"][self.progress]:self.progress+=1;self.store=[]
   else:self.fail()
  elif z==6:
   if self.progress==len(l["modules"]) and not self.store and self.first==l["latent"]:self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()
