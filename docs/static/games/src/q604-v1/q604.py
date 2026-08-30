"""q604 Moraine Grammar -- compose grouped spatial commands through local relays."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GLACIER,RAFT,GROUP,RELATION,RELAY,OUTER,BAD=8,11,9,14,12,15,6,3
LEVELS=[
 {"name":"Grouped Message","commands":[[1,3]],"shifts":[0]},
 {"name":"Relay Transform","commands":[[2,4],[1,3]],"shifts":[1,0]},
 {"name":"Spatial Relation","commands":[[4,2],[3,1],[1,4]],"shifts":[2,1,0]},
 {"name":"Outer Dependency","commands":[[3,4],[1,2],[4,1],[2,3]],"shifts":[1,3,2,0]},
 {"name":"Composed Relay","commands":[[2,1],[4,3],[1,4],[3,2],[2,4]],"shifts":[3,2,1,0,2]},
 {"name":"Moraine Grammar","commands":[[4,1],[2,3],[3,4],[1,2],[4,2],[2,1]],"shifts":[2,0,3,1,2,3]}]
def encode(a,shift):return((a-1+shift)%4)+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=GLACIER;f[15:28,8:22]=RAFT;f[15:28,42:56]=RAFT;f[31:36,8:56]=RELAY
  for i in range(len(g.commands)):x=8+i*7;f[42:47,x:x+5]=OUTER if i<g.progress else GROUP;f[49:53,x:x+5]=RELATION
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q604(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.commands=self.shifts=self.buffer=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q604",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.commands=[list(x) for x in s["commands"]];self.shifts=list(s["shifts"]);self.buffer=[];self.progress=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3,4):self.buffer.append(encode(z,self.shifts[self.progress]))
  elif z==5:
   if self.buffer!=self.commands[self.progress]:self.failed=True;self.lose()
   else:
    self.progress+=1;self.buffer=[]
    if self.progress==len(self.commands):self.next_level()
  self.complete_action()
