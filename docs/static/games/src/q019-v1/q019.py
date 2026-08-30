"""q019 Apprentice Path -- adapt demonstrations to an apprentice's transformation rule."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SCHOOL,TEACHER,APPRENTICE,ROUTE,DONE,RULE,BAD=12,1,9,14,10,6,15,8
LEVELS=[
 {"name":"Copied Step","rule":[1,2,3,4],"route":[1,4]},
 {"name":"Rotated Lesson","rule":[2,3,4,1],"route":[1,2,4]},
 {"name":"Mirror Teaching","rule":[4,3,2,1],"route":[4,1,3,2]},
 {"name":"Incomplete Imitation","rule":[2,1,4,3],"route":[3,1,4,2,1]},
 {"name":"Adapt the Lesson","rule":[3,4,1,2],"route":[4,2,1,3,4,1]},
 {"name":"Apprentice Path","rule":[4,1,2,3],"route":[2,4,1,3,2,1,4]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=SCHOOL;f[16:27,7:18]=TEACHER;f[35:46,7:18]=APPRENTICE
  for i,a in enumerate(g.route):x=23+i*5;f[18:24,x:x+4]=ROUTE;f[38:44,x:x+4]=DONE if i<len(g.result) else APPRENTICE
  for i,r in enumerate(g.rule):f[49:53,24+i*8:30+i*8]=RULE;f[50:52,25+i*8:25+i*8+r]=ROUTE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q019(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rule=self.route=self.result=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q019",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.rule=list(s["rule"]);self.route=list(s["route"]);self.result=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3,4):self.result.append(self.rule[z-1])
  elif z==5:
   if self.result==self.route:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
