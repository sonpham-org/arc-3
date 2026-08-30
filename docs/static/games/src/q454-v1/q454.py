"""q454 Masquerade Thread -- retain identity while masks and positions are rewritten."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BALLROOM,MASK,THREAD,EXIT,CHECK,BAD=3,13,11,15,14,6,8
LEVELS=[{"name":n,"ancestor":a,"ops":ops} for n,a,ops in [
 ("First Exchange",0,(1,)),("Rotating Masks",1,(2,4)),("Crossed Partners",2,(3,1,4)),
 ("False Face",3,(4,2,1,3)),("Lineage Dance",1,(2,3,4,1,2)),("Masquerade Thread",2,(4,1,3,2,4,1))]]
def transform(perm,masks,a):
 p=list(perm);m=list(masks)
 if a==1:p[0],p[1]=p[1],p[0]
 elif a==2:p=p[1:]+p[:1];m=m[1:]+m[:1]
 elif a==3:p[1],p[2]=p[2],p[1]
 else:m=[(x+1)%4 for x in m]
 return tuple(p),tuple(m)
def result(x):
 p,m=(0,1,2,3),(0,1,2,3)
 for a in x["ops"]:p,m=transform(p,m,a)
 return p.index(x["ancestor"]),(sum((i+1)*v for i,v in enumerate(m))+p[0])%4
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=BALLROOM
  for i,(identity,mask) in enumerate(zip(g.perm,g.masks)):
   x=7+i*14;f[15:29,x:x+10]=MASK+mask%3;f[31+identity:34+identity,x:x+10]=THREAD
  f[43:49,7+g.exit*14:17+g.exit*14]=EXIT;f[52:56,7:7+g.check*12]=CHECK
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q454(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.perm=(0,1,2,3);self.masks=(0,1,2,3);self.exit=self.check=0;self.target=(0,0);self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q454",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  self.perm=(0,1,2,3);self.masks=(0,1,2,3);self.exit=self.check=0;self.target=result(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.perm,self.masks=transform(self.perm,self.masks,a)
  elif a==5:self.check=(self.check+1)%4
  elif a==6:
   target_exit,target_check=self.target
   if self.perm[target_exit]==x["ancestor"] and self.check==target_check:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
