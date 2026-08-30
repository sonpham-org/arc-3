"""q023 Broken Symmetry -- locate one asymmetric causal machine with interventions."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,MACHINE,ODD,PROBE,CURSOR,BAD=6,0,10,8,14,11,13
LEVELS=[{"name":n,"odd":o,"responses":r} for n,o,r in [("One Probe",1,[0,1,0]),("Four Twins",3,[1,1,1,0]),("Delayed Defect",0,[2,1,1,1]),("Wrapped Bench",4,[0,0,0,0,2]),("Weak Link",2,[1,1,3,1,1,1]),("Broken Symmetry",5,[2,2,2,2,2,0])]]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,4:60]=LAB;n=len(g.responses)
  for i in range(n):
   x=7+i*(50//n);f[20:38,x:x+7]=MACHINE;f[16:19,x:x+7]=CURSOR if i==g.cursor else LAB
   if i in g.probed:f[41:46,x:x+7]=ODD if g.responses[i]!=g.common else PROBE
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q023(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.responses=[];self.odd=self.cursor=self.common=0;self.probed=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q023",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.responses=list(s["responses"]);self.odd=s["odd"];self.cursor=0;self.common=max(set(self.responses),key=self.responses.count);self.probed=set();self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.responses)
  elif a==4:self.cursor=(self.cursor+1)%len(self.responses)
  elif a==5:self.probed.add(self.cursor)
  elif a==6:
   if self.cursor==self.odd and self.cursor in self.probed:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
