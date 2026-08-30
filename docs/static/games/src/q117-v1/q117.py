"""q117 Teach Back -- learn a tutor transform, then demonstrate it to a simpler agent."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SCHOOL,TUTOR,STUDENT,RULE,ROUTE,LEARNED,BAD=12,1,9,14,15,10,6,8
LEVELS=[
 {"name":"Observe Then Teach","rule":[1,2,3,4],"route":[1,4]},
 {"name":"Rotated Tutor","rule":[2,3,4,1],"route":[4,1,2]},
 {"name":"Teach the Abstraction","rule":[4,3,2,1],"route":[3,1,4,2]},
 {"name":"Student Mistake","rule":[2,1,4,3],"route":[1,3,4,2,1]},
 {"name":"General Lesson","rule":[3,4,1,2],"route":[2,4,1,3,2,1]},
 {"name":"Teach Back","rule":[4,1,2,3],"route":[3,1,4,2,3,2,1]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=SCHOOL;f[15:27,8:20]=TUTOR;f[36:48,8:20]=STUDENT
  for i,r in enumerate(g.rule):x=25+i*8;f[17:23,x:x+6]=LEARNED if i in g.learned else RULE;f[38:44,x:x+6]=ROUTE if i<len(g.result) else SCHOOL
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q117(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rule=self.route=self.result=[];self.learned=set();self.query=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q117",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.rule=list(s["rule"]);self.route=list(s["route"]);self.result=[];self.learned=set();self.query=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==5:self.learned.add(self.query);self.query=(self.query+1)%4
  elif z in (1,2,3,4):
   if len(self.learned)<4:self.failed=True;self.lose()
   else:self.result.append(self.rule[z-1])
  elif z==6:
   if self.result==self.route:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
