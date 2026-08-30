"""q014 Flock Vote -- infer how individual gestures aggregate into group motion."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HALL,BIRD,GESTURE,VOTE,DONE,BAD=7,11,9,12,10,14,8
LEVELS=[
 {"name":"Majority","rule":0,"groups":[[1,1,2],[3,3,1]]}, {"name":"Leader","rule":1,"groups":[[4,2,2],[1,3,4],[2,4,1]]},
 {"name":"Last Voice","rule":2,"groups":[[1,2,3],[4,1,2],[3,3,4],[2,1,1]]}, {"name":"Opposition","rule":3,"groups":[[1,1,1],[2,3,2],[4,4,1],[3,2,3],[1,4,1]]},
 {"name":"Mixed Corridors","rule":0,"groups":[[1,2,1],[4,3,4],[2,2,3],[3,1,3],[4,4,2],[1,3,1]]}, {"name":"Flock Vote","rule":3,"groups":[[1,2,1],[2,4,2],[3,1,3],[4,3,4],[1,4,1],[2,3,2],[4,1,4]]}]
def result(rule,g):
 if rule==0:return max(set(g),key=lambda x:(g.count(x),-g.index(x)))
 if rule==1:return g[0]
 if rule==2:return g[-1]
 return (g[0]+1)%4+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=HALL
  for i,grp in enumerate(g.groups):
   x=7+i*8
   for j,a in enumerate(grp):f[14+j*6:18+j*6,x:x+5]=BIRD;f[15+j*6:17+j*6,x:x+1+a]=GESTURE
   f[40:47,x:x+5]=DONE if i<g.progress else VOTE
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q014(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rule=0;self.groups=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q014",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.rule=s["rule"];self.groups=[list(x) for x in s["groups"]];self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a!=result(self.rule,self.groups[self.progress]):self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.groups):self.next_level()
  self.complete_action()
