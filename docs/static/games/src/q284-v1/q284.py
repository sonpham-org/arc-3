"""q284 Tessera Probe -- diagnose a hidden seam and interrupt an autonomous routine."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MOSAIC,TESSERA,SEAM,PROBE,ROUTINE,WINDOW,BAD=3,13,9,12,15,10,6,8
MODELS=[[1,0,1],[1,1,0],[0,1,1]]
LEVELS=[
 {"name":"Probe the Seam","model":0,"period":5,"window":4,"budget":6},{"name":"Routine Window","model":1,"period":6,"window":5,"budget":5},
 {"name":"Shared Cause","model":2,"period":7,"window":1,"budget":6},{"name":"Macro Interrupt","model":1,"period":8,"window":6,"budget":7},
 {"name":"Topology Test","model":0,"period":9,"window":8,"budget":5},{"name":"Tessera Probe","model":2,"period":10,"window":8,"budget":6}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=MOSAIC
  for i in range(3):x=9+i*17;f[17:31,x:x+11]=TESSERA;f[34:39,x:x+11]=SEAM
  f[3:6,8:8+g.resource*7]=PROBE;f[43:48,8:8+g.phase*5]=ROUTINE;f[50:54,8:8+g.window*5]=WINDOW
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q284(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.model=self.period=self.window=self.resource=self.phase=self.candidate=0;self.responses=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q284",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.model=s["model"];self.period=s["period"];self.window=s["window"];self.resource=s["budget"];self.phase=self.candidate=0;self.responses=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3):self.resource-=1;self.responses.append(MODELS[self.model][z-1]);self.phase=(self.phase+1)%self.period
  elif z==4:self.resource-=1;self.candidate=(self.candidate+1)%3
  elif z==5:self.resource-=1;self.phase=(self.phase+3)%self.period
  elif z==6:
   if self.resource>=0 and len(self.responses)>=2 and self.candidate==self.model and self.phase==self.window:self.next_level()
   else:self.failed=True;self.lose()
  if self.resource<0 and not self.failed:self.failed=True;self.lose()
  self.complete_action()
