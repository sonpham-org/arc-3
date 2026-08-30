"""q212 Lockwater Veil -- attention updates hidden identities beneath swapped appearances."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CANAL,BARGE,LIT,HIDDEN,TRAIL,TARGET,BAD=6,10,9,15,12,3,14,8
LEVELS=[
 {"name":"Hidden Current","start":[0,1],"rates":[1,2],"plan":[2,1]},
 {"name":"Exchange Appearance","start":[2,0],"rates":[2,1],"plan":[3,2,1]},
 {"name":"Track Identity","start":[1,3],"rates":[1,3],"plan":[1,3,2,2]},
 {"name":"Coupled Water","start":[3,1],"rates":[3,2],"plan":[2,3,1,2,3]},
 {"name":"Trail Assignment","start":[0,2],"rates":[2,3],"plan":[3,1,2,3,2,1]},
 {"name":"Lockwater Veil","start":[2,3],"rates":[3,1],"plan":[2,3,1,2,1,3,2]}]
def advance(state,action,rates):
 values,perm,focus=state;values=list(values);perm=list(perm)
 if action==1:focus=1-focus
 elif action==3:perm[0],perm[1]=perm[1],perm[0]
 hidden=perm[1-focus];values[hidden]=(values[hidden]+rates[hidden])%4
 return tuple(values),tuple(perm),focus
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CANAL
  for appearance in range(2):
   x=10+appearance*32;identity=g.perm[appearance];f[17:33,x:x+13]=LIT if appearance==g.focus else HIDDEN;f[29-g.values[identity]*4:32,x+3:x+10]=BARGE;f[39:44,x:x+13]=TRAIL if identity else TARGET
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q212(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.rates=self.target_values=[];self.perm=self.target_perm=[0,1];self.focus=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q212",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=list(s["start"]);self.rates=list(s["rates"]);self.perm=[0,1];self.focus=0;state=(tuple(self.values),tuple(self.perm),0)
  for a in s["plan"]:state=advance(state,a,self.rates)
  self.target_values=list(state[0]);self.target_perm=list(state[1]);self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3):v,p,self.focus=advance((tuple(self.values),tuple(self.perm),self.focus),z,self.rates);self.values=list(v);self.perm=list(p)
  elif z==6:
   if self.values==self.target_values and self.perm==self.target_perm:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
