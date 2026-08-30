"""q124 Counter-Predator -- recent distance policy selects a predictable tactic and counter."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARENA,PREDATOR,HISTORY,COUNTER,DONE,BAD=8,1,13,10,9,14,5
LEVELS=[
 {"name":"Chase Counter","hist":[[1,1]],"map":[2,3,1]}, {"name":"Retreat Counter","hist":[[2,2],[1,2]],"map":[3,1,4]},
 {"name":"Distance Policy","hist":[[3,3],[1,1],[2,3]],"map":[4,2,1]}, {"name":"Adaptive Tactics","hist":[[1,2],[2,2],[3,1],[1,1]],"map":[2,4,3]},
 {"name":"Recent Window","hist":[[2,3],[3,3],[1,2],[2,1],[1,1]],"map":[3,1,4]}, {"name":"Counter-Predator","hist":[[1,3],[2,2],[3,1],[1,1],[2,3],[3,3]],"map":[4,2,1]}]
def tactic(h):return max(set(h),key=lambda x:(h.count(x),h[::-1].index(x)))-1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=ARENA
  for i,h in enumerate(g.hist):x=7+i*8;f[14:21,x:x+6]=PREDATOR;f[25:30,x:x+sum(h)]=HISTORY;f[38:45,x:x+6]=DONE if i<g.progress else COUNTER
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q124(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.hist=[];self.map=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q124",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.hist=[list(x) for x in s["hist"]];self.map=list(s["map"]);self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a!=self.map[tactic(self.hist[self.progress])]:self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.hist):self.next_level()
  self.complete_action()
