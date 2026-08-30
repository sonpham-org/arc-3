"""q455 Puppet Provenance -- track lineage beneath position and costume changes."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,PUPPET,COSTUME,STRING,CHECK,BAD=11,13,12,6,15,14,8
LEVELS=[{"name":n,"ancestor":a,"ops":ops} for n,a,ops in [
 ("First String",0,(1,)),("Costume Wheel",2,(2,3)),("Crossed Puppets",3,(4,1,3)),
 ("False Costume",4,(3,2,1,4)),("Provenance Scene",1,(2,4,3,1,2)),
 ("Puppet Provenance",3,(1,3,4,2,3,1))]]
def transform(perm,costumes,a):
 p=list(perm);c=list(costumes)
 if a==1:p[0],p[-1]=p[-1],p[0]
 elif a==2:p=p[-1:]+p[:-1];c=c[-1:]+c[:-1]
 elif a==3:c=[(x+1)%5 for x in c]
 else:p[1],p[3]=p[3],p[1]
 return tuple(p),tuple(c)
def result(x):
 p,c=tuple(range(5)),tuple(range(5))
 for a in x["ops"]:p,c=transform(p,c,a)
 return p.index(x["ancestor"]),(sum((i+1)*v for i,v in enumerate(c))+p[-1])%5
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=STAGE
  for i,(identity,costume) in enumerate(zip(g.perm,g.costumes)):
   x=6+i*11;f[14:27,x:x+8]=PUPPET if costume%2 else COSTUME;f[7:14,x+3:x+5]=STRING;f[29+identity:32+identity,x:x+8]=STRING
  f[48:53,6+g.target_pos*11:14+g.target_pos*11]=CHECK;f[54:58,6:6+g.check*9]=COSTUME
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q455(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.perm=tuple(range(5));self.costumes=tuple(range(5));self.target_pos=self.check=0;self.target=(0,0);self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q455",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  self.perm=tuple(range(5));self.costumes=tuple(range(5));self.target=result(LEVELS[self.level_index]);self.target_pos=self.target[0];self.check=0;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.perm,self.costumes=transform(self.perm,self.costumes,a)
  elif a==5:self.check=(self.check+1)%5
  elif a==6:
   if self.perm[self.target_pos]==x["ancestor"] and self.check==self.target[1]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
