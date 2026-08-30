"""q278 Asterism Probe -- distinguish causal star links in a resettable evidence-preserving experiment."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SPACE,STAR,LINE,PULSE,EVIDENCE,MODEL,BAD=2,0,15,11,14,12,10,8
LEVELS=[
 {"name":"First Probe","model":0,"test":(1,),"run":(2,)},{"name":"Shared Cause","model":1,"test":(2,1),"run":(1,3)},
 {"name":"Precessing Link","model":2,"test":(3,2),"run":(1,2,3)},{"name":"Reset Experiment","model":3,"test":(1,3,2),"run":(2,1,3,1)},
 {"name":"Irreversible Repair","model":4,"test":(2,3,1,2),"run":(3,1,2,3,1)},{"name":"Asterism Probe","model":5,"test":(1,2,3,1,3),"run":(2,3,1,2,1,3)}]
def pulse(state,a,model):
 s=list(state);s[a-1]=(s[a-1]+1+model%3)%4;s[(a+model)%3]=(s[(a+model)%3]+model//3+1)%4;return tuple(s)
def simulate(plan,model):
 s=(0,1,2)
 for a in plan:s=pulse(s,a,model)
 return s
def checksum(s):return (s[0]+2*s[1]+3*s[2])%7
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SPACE
  for i,v in enumerate(g.state):
   x=9+i*17;f[11:28,x:x+11]=LINE;f[15+v*2:21+v*2,x+3:x+8]=STAR
  f[38:42,8:8+g.evidence*7]=EVIDENCE;f[46:50,8:29 if g.reset_done else 16]=PULSE;f[54:58,8:8+g.candidate*8]=MODEL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q278(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.state=(0,1,2);self.evidence=self.candidate=0;self.reset_done=False;self.target=(0,1,2);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q278",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.state=(0,1,2);self.evidence=self.candidate=0;self.reset_done=False;self.target=simulate(x["run"],x["model"]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.state=pulse(self.state,a,x["model"])
  elif a==4:self.evidence=checksum(self.state)
  elif a==5:
   if not self.reset_done:self.state=(0,1,2);self.reset_done=True
   else:self.candidate=(self.candidate+1)%6
  elif a==6:
   if self.evidence==checksum(simulate(x["test"],x["model"])) and self.reset_done and self.state==self.target and self.candidate==x["model"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
