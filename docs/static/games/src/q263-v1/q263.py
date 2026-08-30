"""q263 Ember Probe -- diagnose hidden heat transmission before one repair."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,VESSEL,HEAT,PROBE,CANDIDATE,REPAIR,BAD=4,13,9,14,15,10,6,8
MODELS=[[1,0,1],[1,1,0],[0,1,1]]
LEVELS=[
 {"name":"Direct or Common","model":0,"budget":3},{"name":"Second Intervention","model":1,"budget":3},
 {"name":"Coincidence Excluded","model":2,"budget":4},{"name":"Shared Resource","model":1,"budget":4},
 {"name":"Irreversible Repair","model":0,"budget":4},{"name":"Ember Probe","model":2,"budget":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=KILN
  for i in range(3):x=9+i*17;f[17:34,x:x+11]=VESSEL;f[37:42,x:x+11]=HEAT if g.responses and g.responses[-1] else KILN
  f[3:6,8:8+g.resource*8]=PROBE;f[47:51,9+g.candidate*17:20+g.candidate*17]=CANDIDATE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q263(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.model=self.resource=self.candidate=0;self.responses=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q263",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.model=s["model"];self.resource=s["budget"];self.candidate=0;self.responses=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3):
   if self.resource<=0:self.failed=True;self.lose()
   else:self.resource-=1;self.responses.append(MODELS[self.model][z-1])
  elif z==4:self.candidate=(self.candidate+1)%3;self.resource-=1
  elif z==5:
   if len(self.responses)>=2 and self.candidate==self.model and self.resource>=0:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  if self.resource<0 and not self.failed:self.failed=True;self.lose()
  self.complete_action()
