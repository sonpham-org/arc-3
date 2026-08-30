"""q387 Canopy Delegation -- alternate complementary observers through a bounded store."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,SEED,SHADE,MARK,STORE,RESULT,BAD=13,7,9,12,15,10,14,8
LEVELS=[
 {"name":"Two Projections","pairs":[[1,2],[2,1]],"capacity":2},
 {"name":"Persistent Mark","pairs":[[2,2],[1,1],[2,1]],"capacity":2},
 {"name":"Bounded Store","pairs":[[1,2],[2,2],[1,1],[2,1]],"capacity":2},
 {"name":"Alternate Control","pairs":[[2,1],[1,2],[2,2],[1,1],[2,1]],"capacity":2},
 {"name":"Avoid Deadlock","pairs":[[1,1],[2,1],[1,2],[2,2],[1,1],[2,2]],"capacity":3},
 {"name":"Canopy Delegation","pairs":[[2,2],[1,2],[2,1],[1,1],[2,2],[1,1],[2,1]],"capacity":3}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=ORCHARD;f[15:29,8:22]=SEED if g.controller==0 else SHADE;f[15:29,42:56]=SHADE if g.controller==0 else SEED
  f[34:39,8:8+(g.mark or 0)*10]=MARK;f[42:47,8:8+len(g.store)*12]=STORE;f[50:54,8:8+len(g.result)*6]=RESULT
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q387(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.pairs=self.store=self.result=[];self.capacity=self.index=self.controller=0;self.mark=None;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q387",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.pairs=[list(x) for x in s["pairs"]];self.capacity=s["capacity"];self.store=[];self.result=[];self.index=self.controller=0;self.mark=None;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2) and self.index<len(self.pairs):
   expected=self.pairs[self.index][self.controller]
   if z!=expected:self.failed=True;self.lose()
   elif self.controller==0:self.mark=z
   elif self.mark is None:self.failed=True;self.lose()
   else:
    self.store.append(self.mark*2+z);self.index+=1;self.mark=None
    if len(self.store)>self.capacity:self.failed=True;self.lose()
  elif z==3:
   if (self.controller==0 and self.mark is not None) or (self.controller==1 and self.mark is None):self.controller=1-self.controller
   else:self.failed=True;self.lose()
  elif z==5 and self.controller==0 and self.mark is None:self.result+=self.store;self.store=[]
  elif z==6:
   if self.index==len(self.pairs) and not self.store and self.result==[a*2+b for a,b in self.pairs]:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
