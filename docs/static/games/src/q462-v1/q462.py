"""q462 Mask Custody -- preserve actor identity while custody masks and positions transform."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,ACTOR,MASK,CUSTODY,CHECK,BAD=11,9,13,15,14,10,8
LEVELS=[
 {"name":"First Mask","actor":0,"ops":(1,)},{"name":"Custody Wheel","actor":1,"ops":(2,3)},
 {"name":"Crossed Masks","actor":2,"ops":(4,1,3)},{"name":"False Face","actor":3,"ops":(3,2,1,4)},
 {"name":"Custody Route","actor":1,"ops":(2,4,3,1,2)},{"name":"Mask Custody","actor":2,"ops":(1,3,4,2,3,1)}]
def transform(actors,masks,a):
 o=list(actors);s=list(masks)
 if a==1:o[0],o[-1]=o[-1],o[0]
 elif a==2:o=o[1:]+o[:1];s=s[-1:]+s[:-1]
 elif a==3:s=[(x+1)%4 for x in s]
 else:o[1],o[2]=o[2],o[1];s[0],s[3]=s[3],s[0]
 return tuple(o),tuple(s)
def result(x):
 o,s=(0,1,2,3),(0,1,2,3)
 for a in x["ops"]:o,s=transform(o,s,a)
 return o.index(x["actor"]),(sum((i+1)*v for i,v in enumerate(s))+o[-1])%4
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=STAGE
  for i,(actor,mask) in enumerate(zip(g.actors,g.masks)):
   x=7+i*14;f[14:28,x:x+10]=ACTOR;f[17:23,x+3:x+7]=MASK if mask%2 else CUSTODY;f[31+actor:34+actor,x:x+10]=CUSTODY
  f[45:51,7+g.target_pos*14:17+g.target_pos*14]=CHECK;f[53:57,7:7+g.check*12]=MASK
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q462(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.actors=(0,1,2,3);self.masks=(0,1,2,3);self.target_pos=self.check=0;self.target=(0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q462",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  self.actors=(0,1,2,3);self.masks=(0,1,2,3);self.target=result(LEVELS[self.level_index]);self.target_pos=self.target[0];self.check=0;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.actors,self.masks=transform(self.actors,self.masks,a)
  elif a==5:self.check=(self.check+1)%4
  elif a==6:
   if self.actors[self.target_pos]==x["actor"] and self.check==self.target[1]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
