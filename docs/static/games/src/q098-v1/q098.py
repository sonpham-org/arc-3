"""q098 Rescue Order -- each rescue unlocks a distinct later capability."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CAVE,AGENT,LOCK,POWER,RESCUED,CURSOR,BAD=2,4,12,8,9,14,11,6
LEVELS=[
 {"name":"First Unlock","deps":[[],[0]],"order":[0,1]},
 {"name":"Hidden Chain","deps":[[],[0],[1]],"order":[0,1,2]},
 {"name":"Forked Rescue","deps":[[],[0],[0],[1,2]],"order":[0,1,2,3]},
 {"name":"Tool Before Door","deps":[[],[],[0,1],[2]],"order":[1,0,2,3]},
 {"name":"Converging Needs","deps":[[],[0],[0],[1,2],[2]],"order":[0,2,1,4,3]},
 {"name":"Rescue Order","deps":[[],[],[0],[1],[2,3],[0,3],[4,5]],"order":[1,3,0,2,5,4,6]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CAVE;n=len(g.deps)
  for i,d in enumerate(g.deps):
   x=7+i*(50//n);f[20:35,x:x+7]=RESCUED if i in g.saved else AGENT;f[15:18,x:x+7]=CURSOR if i==g.cursor else CAVE;f[39:43,x:x+min(7,len(d)*2+2)]=LOCK if not set(d)<=g.saved else POWER
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q098(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.deps=[];self.saved=set();self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q098",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):self.deps=[list(x) for x in LEVELS[self.level_index]["deps"]];self.saved=set();self.cursor=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==3:self.cursor=(self.cursor-1)%len(self.deps)
  elif z==4:self.cursor=(self.cursor+1)%len(self.deps)
  elif z==5:
   if self.cursor not in self.saved and set(self.deps[self.cursor])<=self.saved:self.saved.add(self.cursor)
   else:self.failed=True;self.lose()
  elif z==6:
   if len(self.saved)==len(self.deps):self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
