"""q280 Vault Probe -- diagnose echo causality while two shared quantities remain conserved."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,ECHO,MASS,CHARGE,PULSE,MODEL,BAD=2,13,11,15,14,10,9,8
LEVELS=[
 {"name":"First Probe","model":0,"plan":(1,4)},{"name":"Shared Cause","model":1,"plan":(2,4,1)},
 {"name":"Dual Echo","model":2,"plan":(3,1,4,2)},{"name":"Conserved Repair","model":3,"plan":(1,2,4,3,1)},
 {"name":"Pressure Fork","model":4,"plan":(2,3,1,4,2,1)},{"name":"Vault Probe","model":5,"plan":(3,1,4,2,3,4,1)}]
def advance(s,a,model):
 mass,charge,signal=s;m=list(mass);c=list(charge)
 if a in (1,2,3):
  src=a-1;dm=(src+1+model)%3;dc=(src+2+model)%3
  if m[src]:m[src]-=1;m[dm]+=1
  if c[src]:c[src]-=1;c[dc]+=1
  signal=(signal+a+model)%5
 else:signal=(signal+sum((i+1)*v for i,v in enumerate(m))+sum(c))%5
 return tuple(m),tuple(c),signal
def target(x):
 s=((5,0,0),(4,0,0),0)
 for a in x["plan"]:s=advance(s,a,x["model"])
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=VAULT
  for i,(a,b) in enumerate(zip(g.mass,g.charge)):
   x=8+i*17;f[10:39,x:x+11]=ECHO;f[36-a*3:37,x+1:x+5]=MASS;f[36-b*3:37,x+6:x+10]=CHARGE
  f[45:49,8:8+g.signal*9]=PULSE;f[53:57,8:8+g.candidate*8]=MODEL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q280(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mass=(5,0,0);self.charge=(4,0,0);self.signal=self.candidate=0;self.history=[];self.target=(self.mass,self.charge,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q280",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mass=(5,0,0);self.charge=(4,0,0);self.signal=self.candidate=0;self.history=[];self.target=target(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.mass,self.charge,self.signal=advance((self.mass,self.charge,self.signal),a,x["model"]);self.history.append(a)
  elif a==5:self.candidate=(self.candidate+1)%6
  elif a==6:
   if tuple(self.history)==x["plan"] and (self.mass,self.charge,self.signal)==self.target and self.candidate==x["model"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
