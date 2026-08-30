"""q099 Waypoint Memory -- store reusable local goals as one global route."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MAP,NODE,WAYPOINT,ROUTE,GOAL,CURSOR,BAD=2,4,10,12,9,14,11,8
LEVELS=[
 {"name":"Remember Turn","nodes":4,"path":[1,3]}, {"name":"Reusable Junction","nodes":5,"path":[2,4,1]},
 {"name":"Global Route","nodes":6,"path":[1,4,2,5]}, {"name":"Avoid Greedy Goal","nodes":7,"path":[3,1,5,2,6]},
 {"name":"Waypoint Chain","nodes":8,"path":[2,6,1,5,3,7]}, {"name":"Waypoint Memory","nodes":9,"path":[4,1,7,2,6,3,8]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=MAP
  for i in range(g.nodes):x=7+(i%5)*11;y=16+(i//5)*20;f[y:y+9,x:x+9]=WAYPOINT if i in g.memory else NODE;f[y-4:y-1,x:x+9]=CURSOR if i==g.cursor else MAP
  for i,w in enumerate(g.memory):f[47:51,7+i*7:12+i*7]=ROUTE;f[3:6,47:57]=GOAL
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q099(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.nodes=self.cursor=0;self.path=[];self.memory=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q099",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.nodes=s["nodes"];self.path=list(s["path"]);self.cursor=0;self.memory=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:
   if self.memory:self.memory.pop()
  elif z==3:self.cursor=(self.cursor-1)%self.nodes
  elif z==4:self.cursor=(self.cursor+1)%self.nodes
  elif z==5:
   if self.cursor not in self.memory:self.memory.append(self.cursor)
  elif z==6:
   if self.memory==self.path:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
