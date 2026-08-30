"""q315 Vivarium Ledger -- conserve microfauna while maintaining reciprocal fairness."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VIVARIUM,FAUNA,STRATA,CURSOR,FAIR,TARGET,BAD=4,11,9,12,15,6,14,8
LEVELS=[
 {"name":"Conserved Population","start":[2,1,0],"target":[1,1,1]},{"name":"Fair Exchange","start":[3,0,1],"target":[1,2,1]},
 {"name":"Reciprocity Memory","start":[1,3,0],"target":[2,1,1]},{"name":"Global Ledger","start":[4,0,1],"target":[1,2,2]},
 {"name":"Temperature Strata","start":[2,3,1],"target":[3,1,2]},{"name":"Vivarium Ledger","start":[5,1,1],"target":[2,3,2]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=VIVARIUM
  for i,v in enumerate(g.values):x=9+i*17;f[17:39,x:x+11]=STRATA;f[35-v*4:38,x+3:x+8]=FAUNA;f[43:47,x:x+11]=CURSOR if i==g.cursor else VIVARIUM;f[49:53,x:x+11]=TARGET if v==g.target[i] else VIVARIUM
  if abs(g.counts[0]-g.counts[1])<=1 and sum(g.counts):f[3:6,8:30]=FAIR
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q315(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=[];self.cursor=0;self.counts=[0,0];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q315",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=list(s["start"]);self.target=list(s["target"]);self.cursor=0;self.counts=[0,0];self.failed=False
 def step(self):
  z=self.action.id.value;nxt=(self.cursor+1)%3
  if z==0:self.complete_action();return
  if z==1 and self.values[self.cursor]>0:self.values[self.cursor]-=1;self.values[nxt]+=1;self.counts[0]+=1
  elif z==2 and self.values[nxt]>0:self.values[nxt]-=1;self.values[self.cursor]+=1;self.counts[1]+=1
  elif z==3:self.cursor=nxt
  elif z==6:
   if self.values==self.target and abs(self.counts[0]-self.counts[1])<=1:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
