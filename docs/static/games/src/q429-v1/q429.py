"""q429 Reedbed Revision -- build connectivity while a worn action rule changes."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MARSH,BEETLE,SALT,WEAR,TOOL,LINK,BAD=13,2,9,12,14,10,15,8
LEVELS=[
 {"name":"Wear Boundary","route":[1,2,3,1],"wear":2,"shift":1,"build":[1]},
 {"name":"Constructed Link","route":[2,1,3,2],"wear":2,"shift":2,"build":[0,2]},
 {"name":"Sparse Recalibration","route":[1,3,2,1,3],"wear":2,"shift":1,"build":[1,3]},
 {"name":"Function Changes Route","route":[3,1,2,3,2],"wear":3,"shift":2,"build":[0,2,4]},
 {"name":"Complemented Law","route":[2,3,1,2,1,3],"wear":3,"shift":1,"build":[1,4]},
 {"name":"Reedbed Revision","route":[3,2,1,3,1,2,3],"wear":3,"shift":2,"build":[0,2,5]}]
def expected(spec,i):return((spec["route"][i]-1+(spec["shift"] if i>=spec["wear"] else 0))%3)+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=MARSH;f[16:30,8:22]=BEETLE;f[16:30,42:56]=BEETLE;f[34:39,8:8+g.progress*7]=SALT;f[42:47,8:30]=WEAR if g.progress>=g.spec["wear"] else MARSH;f[49:53,34:56]=LINK if g.connectivity else TOOL
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q429(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.spec={"wear":0,"route":[],"build":[]};self.progress=0;self.built=set();self.connectivity=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q429",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):self.spec=deepcopy(LEVELS[self.level_index]);self.progress=0;self.built=set();self.connectivity=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==4 and self.progress in self.spec["build"] and self.progress not in self.built:self.built.add(self.progress);self.connectivity=not self.connectivity
  elif z in (1,2,3):
   if self.progress in self.spec["build"] and self.progress not in self.built:self.failed=True;self.lose()
   elif z!=expected(self.spec,self.progress):self.failed=True;self.lose()
   else:
    self.progress+=1
    if self.progress==len(self.spec["route"]):
     if len(self.built)==len(self.spec["build"]) and self.connectivity==(len(self.spec["build"])%2==1):self.next_level()
     else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
