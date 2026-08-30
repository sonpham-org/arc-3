"""q458 Caravan Seals -- track ownership identity independently from visible seals."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CAMP,CRATE,SEAL,ROPE,CHECK,BAD=11,13,12,15,14,10,8
LEVELS=[
 {"name":"First Transfer","owner":0,"ops":(1,)},{"name":"Seal Wheel","owner":1,"ops":(2,3)},
 {"name":"Crossed Cargo","owner":2,"ops":(4,1,3)},{"name":"False Seal","owner":3,"ops":(3,2,1,4)},
 {"name":"Ownership Trail","owner":1,"ops":(2,4,3,1,2)},{"name":"Caravan Seals","owner":2,"ops":(1,3,4,2,3,1)}]
def transform(owners,seals,a):
 o=list(owners);s=list(seals)
 if a==1:o[0],o[-1]=o[-1],o[0]
 elif a==2:o=o[1:]+o[:1];s=s[-1:]+s[:-1]
 elif a==3:s=[(x+1)%4 for x in s]
 else:o[1],o[2]=o[2],o[1];s[0],s[3]=s[3],s[0]
 return tuple(o),tuple(s)
def result(x):
 o,s=(0,1,2,3),(0,1,2,3)
 for a in x["ops"]:o,s=transform(o,s,a)
 return o.index(x["owner"]),(sum((i+1)*v for i,v in enumerate(s))+o[-1])%4
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=CAMP
  for i,(owner,seal) in enumerate(zip(g.owners,g.seals)):
   x=7+i*14;f[14:28,x:x+10]=CRATE;f[17:23,x+3:x+7]=SEAL if seal%2 else ROPE;f[31+owner:34+owner,x:x+10]=ROPE
  f[45:51,7+g.target_pos*14:17+g.target_pos*14]=CHECK;f[53:57,7:7+g.check*12]=SEAL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q458(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.owners=(0,1,2,3);self.seals=(0,1,2,3);self.target_pos=self.check=0;self.target=(0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q458",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  self.owners=(0,1,2,3);self.seals=(0,1,2,3);self.target=result(LEVELS[self.level_index]);self.target_pos=self.target[0];self.check=0;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.owners,self.seals=transform(self.owners,self.seals,a)
  elif a==5:self.check=(self.check+1)%4
  elif a==6:
   if self.owners[self.target_pos]==x["owner"] and self.check==self.target[1]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
