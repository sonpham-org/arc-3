"""q439 Monsoon Revision -- revise a worn rule and finish at an unequal-cycle phase pair."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,SEED,STORM,WEAR,CYCLE,TARGET,BAD=8,2,9,12,10,15,6,14
LEVELS=[
 {"name":"Wear Boundary","route":[1,2,3],"wear":1,"shift":1,"mods":[2,3],"target":[1,2]},
 {"name":"Unequal Cycles","route":[2,1,3,2],"wear":2,"shift":2,"mods":[3,4],"target":[2,1]},
 {"name":"Sparse Recalibration","route":[1,3,2,1],"wear":2,"shift":1,"mods":[4,5],"target":[3,4]},
 {"name":"Delayed Storm Rule","route":[3,1,2,3,2],"wear":2,"shift":2,"mods":[5,6],"target":[1,5]},
 {"name":"Phase Pair","route":[2,3,1,2,1,3],"wear":3,"shift":1,"mods":[6,7],"target":[4,2]},
 {"name":"Monsoon Revision","route":[3,2,1,3,1,2,3],"wear":3,"shift":2,"mods":[7,8],"target":[5,7]}]
def expected(s,i):return((s["route"][i]-1+(s["shift"] if i>=s["wear"] else 0))%3)+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=GARDEN;f[16:30,8:22]=SEED;f[16:30,42:56]=STORM;f[34:39,8:8+g.progress*7]=CYCLE;f[42:47,8:8+g.phase[0]*7]=TARGET;f[49:53,8:8+g.phase[1]*5]=CYCLE
  if g.progress>=g.spec["wear"]:f[3:6,8:30]=WEAR
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q439(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.spec={"wear":0,"route":[]};self.progress=0;self.phase=[0,0];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q439",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):self.spec=deepcopy(LEVELS[self.level_index]);self.progress=0;self.phase=[0,0];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3) and self.progress<len(self.spec["route"]):
   if z!=expected(self.spec,self.progress):self.failed=True;self.lose()
   else:self.progress+=1;self.phase=[(p+1)%m for p,m in zip(self.phase,self.spec["mods"])]
  elif z==4:self.phase[0]=(self.phase[0]+1)%self.spec["mods"][0]
  elif z==5:self.phase[1]=(self.phase[1]+1)%self.spec["mods"][1]
  elif z==6:
   if self.progress==len(self.spec["route"]) and self.phase==self.spec["target"]:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
