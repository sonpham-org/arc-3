"""q457 Shell Provenance -- retain creature identity through shell and tide rearrangements."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BEACH,SHELL,PATTERN,TIDE,CHECK,BAD=11,12,14,15,9,10,8
LEVELS=[
 {"name":"First Swap","ancestor":0,"ops":(1,)},{"name":"Pattern Wheel","ancestor":1,"ops":(2,3)},
 {"name":"Crossed Shells","ancestor":2,"ops":(4,1,3)},{"name":"False Pattern","ancestor":3,"ops":(3,2,1,4)},
 {"name":"Provenance Shore","ancestor":1,"ops":(2,4,3,1,2)},{"name":"Shell Provenance","ancestor":2,"ops":(1,3,4,2,3,1)}]
def transform(perm,patterns,a):
 p=list(perm);o=list(patterns)
 if a==1:p[0],p[-1]=p[-1],p[0]
 elif a==2:p=p[1:]+p[:1];o=o[1:]+o[:1]
 elif a==3:o=[(x+1)%4 for x in o]
 else:p[1],p[2]=p[2],p[1]
 return tuple(p),tuple(o)
def result(x):
 p,o=(0,1,2,3),(0,1,2,3)
 for a in x["ops"]:p,o=transform(p,o,a)
 return p.index(x["ancestor"]),(sum((i+1)*v for i,v in enumerate(o))+p[0])%4
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=BEACH
  for i,(identity,pattern) in enumerate(zip(g.perm,g.patterns)):
   x=7+i*14;f[14:28,x:x+10]=SHELL if pattern%2 else PATTERN;f[31+identity:34+identity,x:x+10]=TIDE
  f[45:51,7+g.target_pos*14:17+g.target_pos*14]=CHECK;f[53:57,7:7+g.check*12]=PATTERN
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q457(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.perm=(0,1,2,3);self.patterns=(0,1,2,3);self.target_pos=self.check=0;self.target=(0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q457",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  self.perm=(0,1,2,3);self.patterns=(0,1,2,3);self.target=result(LEVELS[self.level_index]);self.target_pos=self.target[0];self.check=0;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.perm,self.patterns=transform(self.perm,self.patterns,a)
  elif a==5:self.check=(self.check+1)%4
  elif a==6:
   if self.perm[self.target_pos]==x["ancestor"] and self.check==self.target[1]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
