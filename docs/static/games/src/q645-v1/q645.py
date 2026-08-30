"""q645 Vivarium Sandbox -- reset miniature interventions while preserving fair evidence."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VIVARIUM,FAUNA,STRATA,EVIDENCE,FAIR,CANDIDATE,BAD=4,11,9,12,10,6,15,8
RESPONSES=[[0,1],[1,1],[1,0]]
LEVELS=[
 {"name":"Two Terrariums","policy":0},{"name":"Fair Sampling","policy":1},
 {"name":"Persistent Evidence","policy":2},{"name":"Reset Progress","policy":1},
 {"name":"Reciprocal Partner","policy":0},{"name":"Vivarium Sandbox","policy":2}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=VIVARIUM;f[15:30,8:24]=FAUNA;f[15:30,40:56]=FAUNA;f[33:38,8:56]=STRATA;f[42:47,8:8+g.tested*13]=EVIDENCE;f[49:53,8+g.candidate*16:20+g.candidate*16]=CANDIDATE
  if g.counts[0]==g.counts[1] and sum(g.counts):f[3:6,8:30]=FAIR
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q645(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.policy=self.tested=self.progress=self.candidate=0;self.counts=[0,0];self.evidence=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q645",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):self.policy=LEVELS[self.level_index]["policy"];self.tested=self.progress=self.candidate=0;self.counts=[0,0];self.evidence=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2) and self.progress==0:self.evidence.append(RESPONSES[self.policy][z-1]);self.tested|=1<<(z-1);self.counts[z-1]+=1;self.progress=1
  elif z==3 and self.progress==1:self.progress=0
  elif z==4 and self.progress==0:self.candidate=(self.candidate+1)%3
  elif z==5:
   if self.tested==3 and self.progress==0 and self.counts[0]==self.counts[1] and self.candidate==self.policy:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
