"""q759 Reedbed Obligation -- preserve a delayed identity-bound debt through construction."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MARSH,BEETLE,SALT,TOOL,LINK,REWARD,BAD=13,2,9,12,14,15,10,8
LEVELS=[
 {"name":"Borrowed Help","identity":1,"delay":2,"tool":[1,2]},
 {"name":"Identity Bound","identity":2,"delay":2,"tool":[2,1,2]},
 {"name":"Intervening Reward","identity":1,"delay":3,"tool":[1,1,2]},
 {"name":"Function and Route","identity":2,"delay":3,"tool":[2,1,2,2]},
 {"name":"Delayed Obligation","identity":1,"delay":4,"tool":[1,2,1,2,1]},
 {"name":"Reedbed Obligation","identity":2,"delay":4,"tool":[2,1,1,2,1,2]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=MARSH;f[15:29,8:22]=BEETLE;f[15:29,42:56]=BEETLE;f[33:38,8:8+g.reward*10]=REWARD;f[41:46,8:8+len(g.built)*7]=TOOL;f[49:53,8:30]=LINK if g.connectivity else MARSH
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q759(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.identity=self.delay=self.stage=self.reward=0;self.tool=self.built=[];self.obligation=None;self.connectivity=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q759",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.identity=s["identity"];self.delay=s["delay"];self.tool=list(s["tool"]);self.stage=self.reward=0;self.built=[];self.obligation=None;self.connectivity=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if self.stage==0 and z in (1,2):self.obligation=z;self.stage=1
  elif self.stage==1 and z==3:
   self.reward+=1
   if self.reward==self.delay:self.stage=2
  elif self.stage==2 and z in (1,2):
   if z!=self.tool[len(self.built)]:self.failed=True;self.lose()
   else:self.built.append(z);self.connectivity=not self.connectivity
   if len(self.built)==len(self.tool):self.stage=3
  elif self.stage==3 and z in (1,2):
   if z==self.obligation==self.identity:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
