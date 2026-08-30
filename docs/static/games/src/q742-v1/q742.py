"""q742 Tide Obligation -- retain causal identity through delayed rewards before an irreversible return."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BASIN,SHELL,CURRENT,DEBT,EVIDENCE,CLAIM,BAD=9,6,15,12,14,11,13,8
LEVELS=[
 {"name":"First Debt","actor":0,"plan":(1,4)},{"name":"Reversing Current","actor":1,"plan":(2,1,4)},
 {"name":"Delayed Reward","actor":2,"plan":(3,2,4,1)},{"name":"Identity Tide","actor":3,"plan":(1,3,2,4,1)},
 {"name":"Safe Branch","actor":1,"plan":(2,1,3,4,2,1)},{"name":"Tide Obligation","actor":2,"plan":(3,1,2,3,4,1,2)}]
def advance(actors,a):
 o=list(actors)
 if a==1:o[0],o[-1]=o[-1],o[0]
 elif a==2:o=o[1:]+o[:1]
 elif a==3:o[1],o[2]=o[2],o[1]
 return tuple(o)
def result(x):
 o=(0,1,2,3);e=0
 for a in x["plan"]:
  if a in (1,2,3):o=advance(o,a)
  else:e|=1<<o.index(x["actor"])
 return o,o.index(x["actor"]),e
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=BASIN
  for i,actor in enumerate(g.actors):
   x=7+i*14;f[13:27,x:x+10]=SHELL;f[29+actor:32+actor,x:x+10]=CURRENT
  if g.evidence:f[40:45,7:7+bin(g.evidence).count('1')*12]=EVIDENCE
  f[49:54,7+g.claim*14:17+g.claim*14]=CLAIM;f[56:60,7:7+(g.debt+1)*10]=DEBT
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q742(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.actors=(0,1,2,3);self.debt=self.claim=self.evidence=0;self.history=[];self.target=((0,1,2,3),0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q742",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.actors=(0,1,2,3);self.debt=x["actor"];self.claim=self.evidence=0;self.history=[];self.target=result(x);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.actors=advance(self.actors,a);self.history.append(a)
  elif a==4:self.evidence|=1<<self.actors.index(self.debt);self.history.append(a)
  elif a==5:self.claim=(self.claim+1)%4
  elif a==6:
   if tuple(self.history)==x["plan"] and self.actors==self.target[0] and self.evidence==self.target[2] and self.claim==self.target[1]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
