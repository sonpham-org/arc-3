"""q094 Delivery Tree -- reveal and satisfy upstream dependencies in a branching network."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,DEPOT,NODE,READY,DONE,TARGET,CURSOR,BAD=15,12,3,10,14,6,11,8
LEVELS=[
 {"name":"One Dependency","parents":[[],[0]],"target":1}, {"name":"Two Sources","parents":[[],[],[0,1]],"target":2},
 {"name":"Branch Request","parents":[[],[],[0],[1],[2,3]],"target":4}, {"name":"Hidden Upstream","parents":[[],[],[0],[0,1],[2,3]],"target":4},
 {"name":"Delivery Network","parents":[[],[],[0],[1],[2,3],[2],[4,5]],"target":6}, {"name":"Delivery Tree","parents":[[],[],[0],[0],[1,2],[2,3],[4,5]],"target":6}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,4:60]=DEPOT;n=len(g.parents)
  for i,p in enumerate(g.parents):
   x=7+i*(49//n);f[27:36,x:x+7]=DONE if i in g.done else READY if all(j in g.done for j in p) else NODE;f[22:25,x:x+7]=TARGET if i==g.target else DEPOT;f[39:43,x:x+7]=CURSOR if i==g.cursor else DEPOT
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q094(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.parents=[];self.target=self.cursor=0;self.done=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q094",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.parents=[list(x) for x in s["parents"]];self.target=s["target"];self.cursor=0;self.done=set();self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.parents)
  elif a==4:self.cursor=(self.cursor+1)%len(self.parents)
  elif a==5:
   if all(x in self.done for x in self.parents[self.cursor]):self.done.add(self.cursor)
   else:self.failed=True;self.lose()
  elif a==6:
   if self.target in self.done:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
