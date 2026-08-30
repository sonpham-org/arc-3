"""q018 Exchange Circle -- infer preferences and arrange a mutually acceptable trade cycle."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HALL,AGENT,BUNDLE,ACCEPT,REJECT,CURSOR,BAD=10,1,12,9,14,8,11,13
LEVELS=[
 {"name":"Mutual Swap","target":[1,0]}, {"name":"Three-Way Cycle","target":[2,0,1]},
 {"name":"Partial Order","target":[1,3,0,2]}, {"name":"Competing Bundles","target":[3,0,4,1,2]},
 {"name":"Preference Ring","target":[2,5,1,4,0,3]}, {"name":"Exchange Circle","target":[4,1,6,0,5,2,3]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,4:60]=HALL;n=len(g.target)
  for i,b in enumerate(g.assignment):
   x=7+i*(50//n);f[16:27,x:x+7]=AGENT;f[33:43,x:x+7]=BUNDLE+(b%3);f[12:15,x:x+7]=CURSOR if i==g.cursor else HALL
   if i in g.revealed:f[47:51,x:x+7]=ACCEPT if b in g.accepts[i] else REJECT
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q018(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=self.assignment=[];self.accepts=[];self.cursor=0;self.revealed=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q018",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  self.target=list(LEVELS[self.level_index]["target"]);n=len(self.target);self.assignment=list(range(n));self.accepts=[{t,(t+1)%n} for t in self.target];self.cursor=0;self.revealed=set();self.failed=False
 def step(self):
  z=self.action.id.value;n=len(self.target)
  if z==0:self.complete_action();return
  if z==1:self.assignment[self.cursor]=(self.assignment[self.cursor]-1)%n
  elif z==2:self.assignment[self.cursor]=(self.assignment[self.cursor]+1)%n
  elif z==3:self.cursor=(self.cursor-1)%n
  elif z==4:self.cursor=(self.cursor+1)%n
  elif z==5:self.revealed.add(self.cursor)
  elif z==6:
   if self.assignment==self.target and len(set(self.assignment))==n and all(b in self.accepts[i] for i,b in enumerate(self.assignment)):self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
