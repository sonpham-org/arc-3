"""q118 Distributed Lesson -- compose policy components demonstrated by different tutors."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CLASS,TUTOR,COMPONENT,FINAL,LEARNED,DONE,BAD=12,1,9,15,14,6,10,8
LEVELS=[
 {"name":"Two Tutors","maps":[[1,2,3,4],[2,3,4,1]],"route":[1,4]},
 {"name":"Three Components","maps":[[2,3,4,1],[1,4,3,2],[3,4,1,2]],"route":[2,1,4]},
 {"name":"Compose Lessons","maps":[[4,3,2,1],[2,1,4,3],[1,3,2,4]],"route":[4,1,3,2]},
 {"name":"Final Room","maps":[[2,1,4,3],[3,4,1,2],[4,2,3,1]],"route":[3,1,4,2,1]},
 {"name":"Distributed Policy","maps":[[3,4,1,2],[1,3,2,4],[2,4,1,3]],"route":[4,2,1,3,4,1]},
 {"name":"Distributed Lesson","maps":[[4,1,2,3],[2,3,1,4],[3,1,4,2]],"route":[2,4,1,3,2,1,4]}]
def compose(a,maps):
 for m in maps:a=m[a-1]
 return a
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CLASS
  for i in range(len(g.maps)):x=8+i*16;f[15:27,x:x+11]=TUTOR;f[30:34,x:x+11]=LEARNED if i<g.observed else COMPONENT
  for i in range(len(g.route)):x=8+i*7;f[44:50,x:x+5]=DONE if i<len(g.result) else FINAL
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q118(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.maps=[];self.route=self.result=[];self.observed=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q118",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.maps=[list(x) for x in s["maps"]];self.route=list(s["route"]);self.result=[];self.observed=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==5:self.observed=min(len(self.maps),self.observed+1)
  elif z in (1,2,3,4):
   if self.observed<len(self.maps):self.failed=True;self.lose()
   else:self.result.append(compose(z,self.maps))
  elif z==6:
   if self.result==self.route:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
