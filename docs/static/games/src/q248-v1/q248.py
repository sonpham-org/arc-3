"""q248 Asterism Pact -- infer a social convention across an evidence-preserving physical reset."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SPACE,STAR,LINE,OFFER,EVIDENCE,ROLE,BAD=1,0,15,11,14,12,10,8
LEVELS=[
 {"name":"First Offer","role":0,"test":(1,),"run":(2,)},{"name":"Reset Convention","role":1,"test":(2,1),"run":(1,3)},
 {"name":"Reciprocal Orbit","role":2,"test":(3,2),"run":(1,2,3)},{"name":"Precessing Pact","role":1,"test":(1,3,2),"run":(2,1,3,1)},
 {"name":"Evidence Contract","role":0,"test":(2,3,1,2),"run":(3,1,2,3,1)},{"name":"Asterism Pact","role":2,"test":(1,2,3,1,3),"run":(2,3,1,2,1,3)}]
def offer(state,a,role):return (state+a+role*(a+1))%7
def simulate(plan,role):
 s=0
 for a in plan:s=offer(s,a,role)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SPACE
  for i in range(3):f[11:27,9+i*17:20+i*17]=STAR if g.seen&(1<<i) else LINE
  f[34:39,8:8+g.state*7]=OFFER;f[43:48,8:8+g.evidence*7]=EVIDENCE;f[52:56,8:29 if g.reset_done else 16]=LINE;f[57:60,8:8+g.candidate*14]=ROLE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q248(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.state=self.seen=self.evidence=self.candidate=0;self.reset_done=False;self.target=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q248",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.state=self.seen=self.evidence=self.candidate=0;self.reset_done=False;self.target=simulate(x["run"],x["role"]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.state=offer(self.state,a,x["role"]);self.seen|=1<<(a-1)
  elif a==4:self.evidence=self.state
  elif a==5:
   if not self.reset_done:self.state=self.seen=0;self.reset_done=True
   else:self.candidate=(self.candidate+1)%3
  elif a==6:
   if self.evidence==simulate(x["test"],x["role"]) and self.reset_done and self.state==self.target and self.candidate==x["role"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
