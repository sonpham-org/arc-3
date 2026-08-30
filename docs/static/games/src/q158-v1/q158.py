"""q158 Causal Rhyme -- transfer cause-effect order across unrelated mechanisms."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,CAUSE,EFFECT,LINK,ACTIVE,DONE,BAD=9,1,12,14,3,10,15,8
BASE=[1,3,2,4]
LEVELS=[
 {"name":"Mechanical Rhyme","perm":[1,2,3,4],"style":0}, {"name":"Biological Rhyme","perm":[2,4,1,3],"style":1},
 {"name":"Signal Rhyme","perm":[3,1,4,2],"style":2}, {"name":"Spatial Rhyme","perm":[4,2,3,1],"style":3},
 {"name":"Abstract Order","perm":[2,3,4,1],"style":4}, {"name":"Causal Rhyme","perm":[3,4,2,1],"style":5}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=FIELD
  for i in range(4):x=9+i*13;f[18:31,x:x+8]=ACTIVE if i<g.progress else CAUSE if (i+g.style)%2 else EFFECT;f[35:39,x:x+8]=LINK
  f[3:6,8:8+g.style*7]=DONE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q158(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.route=[];self.style=self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q158",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
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
