"""q680 Workbench Analogy -- transfer fixture relations while tracking identity-bound obligations."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WORKSHOP,FIXTURE,TOOL,RELATION,DEBT,CLAIM,BAD=6,13,11,15,14,12,9,8
LEVELS=[
 {"name":"First Borrow","ops":(4,),"actor":1},{"name":"Rotated Fixture","ops":(2,4,1),"actor":2},
 {"name":"Surface Transfer","ops":(3,4,2,1),"actor":1},{"name":"Relational Tool","ops":(1,3,4,2,3),"actor":1},
 {"name":"Delayed Return","ops":(2,4,3,1,2,3),"actor":2},{"name":"Workbench Analogy","ops":(1,3,2,4,1,2,3),"actor":2}]
def transform(actors,tools,debt,a):
 o=list(actors);t=list(tools)
 if a==1:o[0],o[-1]=o[-1],o[0]
 elif a==2:o=o[1:]+o[:1];t=t[-1:]+t[:-1]
 elif a==3:t=[(x+1)%4 for x in t]
 else:debt=o[1];t[1],t[2]=t[2],t[1]
 return tuple(o),tuple(t),debt
def result(x):
 o,t,d=(0,1,2,3),(0,1,2,3),-1
 for a in x["ops"]:o,t,d=transform(o,t,d,a)
 return o.index(d),(sum((i+1)*v for i,v in enumerate(t))+d)%4
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=WORKSHOP
  for i,(actor,tool) in enumerate(zip(g.actors,g.tools)):
   x=7+i*14;f[13:27,x:x+10]=FIXTURE;f[16:23,x+3:x+7]=TOOL if tool%2 else RELATION;f[29+actor:32+actor,x:x+10]=RELATION
  if g.debt>=0:f[43:48,7+g.actors.index(g.debt)*14:17+g.actors.index(g.debt)*14]=DEBT
  f[52:57,7+g.claim*14:17+g.claim*14]=CLAIM
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q680(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.actors=(0,1,2,3);self.tools=(0,1,2,3);self.debt=-1;self.claim=self.check=0;self.target=(0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q680",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.actors=(0,1,2,3);self.tools=(0,1,2,3);self.debt=-1;self.claim=self.check=0;self.target=result(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.actors,self.tools,self.debt=transform(self.actors,self.tools,self.debt,a)
  elif a==5:self.claim=(self.claim+1)%4;self.check=(self.check+1)%4
  elif a==6:
   if self.debt==x["actor"] and self.actors[self.claim]==self.debt and self.target[1]==(sum((i+1)*v for i,v in enumerate(self.tools))+self.debt)%4:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
