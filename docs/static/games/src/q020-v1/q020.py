"""q020 Crowd Current -- diagnose and reshape crowds governed by distinct local rules."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,PLAZA,CROWD,PROBE,TARGET,RULE,CURSOR,BAD=10,1,12,9,14,15,11,8
LEVELS=[
 {"name":"Alignment Probe","rule":0,"start":[1,2,0],"plan":[1]},
 {"name":"Avoidance Flow","rule":1,"start":[2,1,1],"plan":[1,2]},
 {"name":"Attraction Center","rule":2,"start":[1,1,2],"plan":[3,2]},
 {"name":"Mixed Density","rule":0,"start":[2,3,1],"plan":[2,1,3]},
 {"name":"Reshape the Crowd","rule":1,"start":[3,2,2],"plan":[3,1,2,1]},
 {"name":"Crowd Current","rule":2,"start":[2,3,3],"plan":[1,3,2,2,1]}]
def apply(vals,rule,action):
 out=list(vals);t=action-1
 if rule==0:src=(t+1)%3;dst=t
 elif rule==1:src=t;dst=(t+1)%3
 else:src=(t-1)%3;dst=t
 if out[src]:out[src]-=1;out[dst]+=1
 return tuple(out)
def derive(level):
 v=tuple(level["start"])
 for a in level["plan"]:v=apply(v,level["rule"],a)
 return v
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=PLAZA
  for i,(v,t) in enumerate(zip(g.values,g.target)):
   x=10+i*17;f[39-v*5:40,x:x+10]=CROWD;f[14:18,x:x+t*3]=TARGET;f[44:48,x:x+10]=CURSOR if i==g.last-1 else PLAZA
  f[3:6,8:18]=[PROBE,CROWD,RULE][g.rule] if g.tested else PROBE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q020(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=();self.rule=self.last=0;self.tested=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q020",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=tuple(s["start"]);self.target=derive(s);self.rule=s["rule"];self.last=0;self.tested=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3):self.values=apply(self.values,self.rule,z);self.last=z
  elif z==5:self.tested=True
  elif z==6:
   if self.tested and self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
