"""q398 Asterism Delegation -- preserve combined remote evidence across a physical reset."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHART,STAR,LINE,MARK,EVIDENCE,RESET,BAD=12,3,9,15,10,14,6,8
LEVELS=[
 {"name":"Complementary Views","pairs":[[1,2],[2,1]]},{"name":"Persistent Mark","pairs":[[2,2],[1,1],[2,1]]},
 {"name":"Evidence Survives","pairs":[[1,2],[2,2],[1,1],[2,1]]},{"name":"Reset the Chart","pairs":[[2,1],[1,2],[2,2],[1,1],[2,1]]},
 {"name":"Experiment Then Act","pairs":[[1,1],[2,1],[1,2],[2,2],[1,1],[2,2]]},{"name":"Asterism Delegation","pairs":[[2,2],[1,2],[2,1],[1,1],[2,2],[1,1],[2,1]]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CHART;f[16:30,8:22]=STAR if g.controller==0 else LINE;f[16:30,42:56]=LINE if g.controller==0 else STAR;f[34:39,8:8+(g.mark or 0)*10]=MARK;f[43:48,8:8+len(g.evidence)*6]=EVIDENCE
  if g.stage:f[50:54,34:56]=RESET
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q398(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.pairs=[];self.index=self.controller=self.stage=0;self.mark=None;self.evidence=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q398",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5,6])
 def on_set_level(self,l):self.pairs=[list(x) for x in LEVELS[self.level_index]["pairs"]];self.index=self.controller=self.stage=0;self.mark=None;self.evidence=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2) and self.index<len(self.pairs):
   if z!=self.pairs[self.index][self.controller]:self.failed=True;self.lose()
   elif self.controller==0:self.mark=z
   elif self.mark is None:self.failed=True;self.lose()
   else:
    code=self.mark*2+z
    if self.stage==0:self.evidence.append(code)
    elif code!=self.evidence[self.index]:self.failed=True;self.lose()
    self.index+=1;self.mark=None
  elif z==3:
   if (self.controller==0 and self.mark is not None) or (self.controller==1 and self.mark is None):self.controller=1-self.controller
   else:self.failed=True;self.lose()
  elif z==5 and self.stage==0 and self.index==len(self.pairs):self.stage=1;self.index=self.controller=0;self.mark=None
  elif z==6:
   if self.stage==1 and self.index==len(self.pairs):self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
