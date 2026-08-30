"""q157 Same Graph New Bodies -- preserve a causal graph across new embodiments."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,NODEA,NODEB,EDGE,ACTIVE,DONE,BAD=9,1,10,12,3,14,15,8
BASE=[1,2,4,3]
LEVELS=[
 {"name":"Graph in Blocks","perm":[1,2,3,4],"style":0}, {"name":"Graph in Creatures","perm":[2,4,1,3],"style":1},
 {"name":"Graph in Lights","perm":[3,1,4,2],"style":2}, {"name":"Graph in Motion","perm":[4,2,3,1],"style":3},
 {"name":"New Embedding","perm":[2,3,4,1],"style":4}, {"name":"Same Graph New Bodies","perm":[3,4,2,1],"style":5}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=FIELD
  pts=[(12,18),(42,16),(16,39),(44,40)]
  for i,(x,y) in enumerate(pts):w=7+(g.style+i)%4;f[y:y+8,x:x+w]=ACTIVE if i<g.progress else NODEA if (g.style+i)%2 else NODEB
  f[29:33,16:48]=EDGE;f[3:6,8:8+g.style*7]=DONE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q157(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.route=[];self.style=self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q157",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.route=[s["perm"][i-1] for i in BASE];self.style=s["style"];self.progress=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z!=self.route[self.progress]:self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.route):self.next_level()
  self.complete_action()
