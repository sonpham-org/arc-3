"""q168 Calibration Orchard -- allocate plants according to stable noisy likelihoods."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,BIN,PLANT,LIKELIHOOD,TARGET,CURSOR,BAD=7,1,12,14,10,15,11,6
LEVELS=[
 {"name":"Likelihood Not Certainty","target":[1,2]}, {"name":"Noisy Growth","target":[2,1,2]},
 {"name":"Calibrated Allocation","target":[1,3,2]}, {"name":"Compare Rates","target":[2,1,3,2]},
 {"name":"Stable Frequencies","target":[1,2,4,2]}, {"name":"Calibration Orchard","target":[2,3,1,4,2]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=ORCHARD;n=len(g.target)
  for i,(v,t) in enumerate(zip(g.values,g.target)):x=8+i*(48//n);f[19:42,x:x+9]=BIN;f[36-v*4:39,x+2:x+7]=PLANT;f[13:16,x:x+t*2]=LIKELIHOOD;f[46:50,x:x+9]=CURSOR if i==g.cursor else ORCHARD
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q168(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=self.values=[];self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q168",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,6])
 def on_set_level(self,l):self.target=list(LEVELS[self.level_index]["target"]);self.values=[0]*len(self.target);self.cursor=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.values[self.cursor]+=1
  elif z==2:self.values[self.cursor]=max(0,self.values[self.cursor]-1)
  elif z==3:self.cursor=(self.cursor-1)%len(self.values)
  elif z==4:self.cursor=(self.cursor+1)%len(self.values)
  elif z==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
