"""q116 Counterexample Room -- select examples that eliminate resembling but wrong policies."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ROOM,RULE,EXAMPLE,PASS,FAIL,CURSOR,BAD=15,1,10,12,14,8,11,6
LEVELS=[
 {"name":"One Counterexample","rules":[0,1],"target":1,"examples":2,"limit":1},
 {"name":"Reject Resemblance","rules":[1,2,3],"target":1,"examples":3,"limit":1},
 {"name":"Two Exceptions","rules":[0,3,5,6],"target":2,"examples":3,"limit":2},
 {"name":"Minority Evidence","rules":[0,1,2,4,7],"target":4,"examples":3,"limit":2},
 {"name":"Rule Elimination","rules":[1,2,4,8,11,13],"target":5,"examples":4,"limit":2},
 {"name":"Counterexample Room","rules":[0,3,5,6,9,10,12,15],"target":6,"examples":4,"limit":3}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=ROOM
  for i in range(g.examples):x=8+i*12;f[16:27,x:x+9]=EXAMPLE;f[12:15,x:x+9]=CURSOR if i==g.example else ROOM;f[30:34,x:x+9]=PASS if i in g.used and g.rules[g.target]&(1<<i) else FAIL if i in g.used else ROOM
  for i in range(len(g.rules)):x=7+i*7;f[43:50,x:x+5]=RULE;f[52:55,x:x+5]=CURSOR if i==g.hyp else ROOM
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q116(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rules=[];self.target=self.examples=self.limit=self.example=self.hyp=0;self.used=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q116",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.rules=list(s["rules"]);self.target=s["target"];self.examples=s["examples"];self.limit=s["limit"];self.example=self.hyp=0;self.used=set();self.failed=False
 def unique(self):
  t=self.rules[self.target];return all(i==self.target or any(((t>>b)&1)!=((v>>b)&1) for b in self.used) for i,v in enumerate(self.rules))
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.example=(self.example-1)%self.examples
  elif z==2:self.example=(self.example+1)%self.examples
  elif z==3:self.hyp=(self.hyp-1)%len(self.rules)
  elif z==4:self.hyp=(self.hyp+1)%len(self.rules)
  elif z==5:
   if self.example not in self.used and len(self.used)<self.limit:self.used.add(self.example)
   else:self.failed=True;self.lose()
  elif z==6:
   if self.hyp==self.target and self.unique():self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
