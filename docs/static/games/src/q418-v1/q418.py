"""q418 Breakwater Revision -- revise a worn rule and account for a dormant seal."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,SKIFF,GATE,WEAR,SEALED,DONE,BAD=1,10,9,12,14,15,6,8
LEVELS=[
 {"name":"Visible Wear","route":[1,2,3,4],"wear":2,"shift":1,"seal":False},
 {"name":"Inverted Channel","route":[2,1,4,3],"wear":2,"shift":2,"seal":True},
 {"name":"Sparse Recalibration","route":[1,3,2,4,1],"wear":2,"shift":3,"seal":False},
 {"name":"Dormant Intervention","route":[4,2,1,3,2],"wear":2,"shift":1,"seal":True},
 {"name":"Delayed Terminal Effect","route":[3,1,4,2,3,1],"wear":3,"shift":2,"seal":True},
 {"name":"Breakwater Revision","route":[2,4,1,3,2,1,4],"wear":3,"shift":3,"seal":False}]
def expected(s,i,sealed):
 z=s["route"][i]
 if i>=s["wear"]:z=((z-1+s["shift"])%4)+1
 if i==len(s["route"])-1 and sealed:z=(z%4)+1
 return z
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=HARBOR;f[16:29,8:22]=SKIFF;f[16:29,42:56]=GATE;f[34:39,8:8+g.progress*7]=DONE;f[43:48,8:30]=WEAR if g.progress>=g.spec["wear"] else HARBOR
  if g.sealed:f[49:53,34:56]=SEALED
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q418(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.spec={"wear":0,"route":[]};self.progress=0;self.sealed=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q418",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):self.spec=deepcopy(LEVELS[self.level_index]);self.progress=0;self.sealed=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==5 and self.progress==0:self.sealed=True
  elif z in (1,2,3,4):
   if z!=expected(self.spec,self.progress,self.sealed):self.failed=True;self.lose()
   else:
    self.progress+=1
    if self.progress==len(self.spec["route"]):
     if self.sealed==self.spec["seal"]:self.next_level()
     else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
