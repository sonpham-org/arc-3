"""q222 Semaphore Veil -- schedule occluded updates after testing two mini systems."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CLIFF,FLAG,LIT,HIDDEN,TESTED,TARGET,BAD=1,10,9,15,12,6,14,8
LEVELS=[
 {"name":"Test Then Observe","start":[0,1,2],"rates":[1,1,1],"plan":[3,2]},
 {"name":"Two Miniatures","start":[2,0,1],"rates":[1,2,1],"plan":[1,3,2]},
 {"name":"Occluded Relay","start":[1,3,0],"rates":[2,1,3],"plan":[2,3,1,3]},
 {"name":"Commit One Policy","start":[3,1,2],"rates":[1,3,2],"plan":[1,3,3,2,1]},
 {"name":"Coupled Sightlines","start":[0,2,3],"rates":[3,1,2],"plan":[2,3,1,2,3,1]},
 {"name":"Semaphore Veil","start":[2,3,1],"rates":[2,3,1],"plan":[3,1,2,3,2,1,3]}]
def advance(values,focus,action,rates):
 if action==1:focus=(focus-1)%3
 elif action==2:focus=(focus+1)%3
 return tuple(v if i==focus else (v+rates[i])%4 for i,v in enumerate(values)),focus
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CLIFF
  for i,v in enumerate(g.values):x=8+i*17;f[16:33,x:x+13]=LIT if i==g.focus else HIDDEN;f[29-v*4:32,x+3:x+10]=FLAG;f[39:44,x:x+13]=TARGET if v==g.target[i] else CLIFF
  f[48:52,8:8+g.tested*12]=TESTED
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q222(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.rates=self.target=[];self.focus=self.tested=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q222",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=list(s["start"]);self.rates=list(s["rates"]);self.focus=self.tested=0;v=tuple(self.values);p=0
  for a in s["plan"]:v,p=advance(v,p,a,self.rates)
  self.target=list(v);self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3):v,self.focus=advance(tuple(self.values),self.focus,z,self.rates);self.values=list(v)
  elif z==4:self.tested|=1
  elif z==5:self.tested|=2
  elif z==6:
   if self.values==self.target and self.tested==3:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
