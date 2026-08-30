"""q201 Aurora Veil -- attention freezes one region while hidden regions evolve."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ICE,MOTE,LIT,HIDDEN,TARGET,TRAIL,BAD=14,10,9,15,12,6,3,8
LEVELS=[
 {"name":"Freeze One Region","start":[0,1,2],"rates":[1,1,1],"plan":[5,2]},
 {"name":"Sweep the Curtain","start":[2,0,1],"rates":[1,2,1],"plan":[1,5,2]},
 {"name":"Coupled Occlusion","start":[1,3,0],"rates":[2,1,3],"plan":[2,5,1,5]},
 {"name":"Irreversible Sweep","start":[3,1,2],"rates":[1,3,2],"plan":[1,5,5,2,1]},
 {"name":"Visible Hysteresis","start":[0,2,3],"rates":[3,1,2],"plan":[2,5,1,2,5,1]},
 {"name":"Aurora Veil","start":[2,3,1],"rates":[2,3,1],"plan":[5,1,2,5,2,1,5]}]
def advance(values,focus,action,rates):
 if action==1:focus=(focus-1)%3
 elif action==2:focus=(focus+1)%3
 values=tuple(v if i==focus else (v+rates[i])%4 for i,v in enumerate(values));return values,focus
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=ICE
  for i,v in enumerate(g.values):x=8+i*17;f[17:36,x:x+13]=LIT if i==g.focus else HIDDEN;f[32-v*4:35,x+3:x+10]=MOTE;f[42:46,x:x+13]=TARGET if v==g.target[i] else TRAIL
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q201(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.rates=self.target=[];self.focus=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q201",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=list(s["start"]);self.rates=list(s["rates"]);self.focus=0;v=tuple(self.values);p=0
  for a in s["plan"]:v,p=advance(v,p,a,self.rates)
  self.target=list(v);self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,5):
   values,self.focus=advance(tuple(self.values),self.focus,z,self.rates);self.values=list(values)
  elif z==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
