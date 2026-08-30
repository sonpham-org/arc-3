"""q274 Moraine Probe -- diagnose a hidden link while a local solve changes an outer token."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GLACIER,RAFT,CREVASSE,PROBE,OUTER,CANDIDATE,BAD=8,11,9,12,15,10,14,3
MODELS=[[1,0,1],[1,1,0],[0,1,1]]
LEVELS=[
 {"name":"Probe the Link","model":0,"outer":2,"budget":5},{"name":"Shared Cause","model":1,"outer":2,"budget":7},
 {"name":"Local Enclosure","model":2,"outer":1,"budget":7},{"name":"Outer Dependency","model":1,"outer":2,"budget":6},
 {"name":"Budgeted Repair","model":0,"outer":3,"budget":7},{"name":"Moraine Probe","model":2,"outer":2,"budget":8}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=GLACIER
  for i in range(3):x=9+i*17;f[17:31,x:x+11]=RAFT;f[34:39,x:x+11]=CREVASSE
  f[3:6,8:8+g.resource*6]=PROBE;f[43:48,8:8+g.outer*10]=OUTER;f[49:53,34:56]=CANDIDATE if g.candidate else GLACIER
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q274(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.model=self.target_outer=self.resource=self.outer=self.candidate=0;self.responses=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q274",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.model=s["model"];self.target_outer=s["outer"];self.resource=s["budget"];self.outer=self.candidate=0;self.responses=[];self.failed=False
 def spend(self):
  self.resource-=1
  if self.resource<0:self.failed=True;self.lose();return False
  return True
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3) and self.spend():self.responses.append(MODELS[self.model][z-1])
  elif z==4 and self.spend():self.outer=(self.outer+self.model+1)%4
  elif z==5 and self.spend():self.candidate=(self.candidate+1)%3
  elif z==6:
   if len(self.responses)>=2 and self.candidate==self.model and self.outer==self.target_outer:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
