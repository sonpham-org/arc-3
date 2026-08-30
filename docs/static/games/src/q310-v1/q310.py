"""q310 Vault Ledger -- conserve two independent quantities inside shared echo containers."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,ECHO,MASS,CHARGE,LEDGER,GOAL,BAD=3,13,11,15,14,10,9,8
LEVELS=[
 {"name":"First Echo","a":4,"b":3,"plan":(1,)},{"name":"Shared Vessel","a":5,"b":4,"plan":(1,2)},
 {"name":"Dual Transfer","a":6,"b":5,"plan":(2,3,1)},{"name":"Pressure Ledger","a":7,"b":6,"plan":(1,3,2,1)},
 {"name":"Coupled Containers","a":8,"b":7,"plan":(2,1,3,2,1)},{"name":"Vault Ledger","a":9,"b":8,"plan":(1,2,3,1,3,2)}]
def advance(s,a):
 x,y=s;x=list(x);y=list(y);src=a-1;dx=(src+1)%3;dy=(src+2)%3
 if x[src]:x[src]-=1;x[dx]+=1
 if y[src]:y[src]-=1;y[dy]+=1
 return tuple(x),tuple(y)
def target(z):
 s=((z["a"],0,0),(z["b"],0,0))
 for a in z["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=VAULT
  for i,(a,b) in enumerate(zip(g.mass,g.charge)):
   x=8+i*17;f[10:39,x:x+11]=ECHO;f[36-a*3:37,x+1:x+5]=MASS;f[36-b*3:37,x+6:x+10]=CHARGE
  f[46:50,8:8+sum(g.mass)*4]=LEDGER;f[53:57,8:8+sum(g.charge)*4]=GOAL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q310(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mass=(4,0,0);self.charge=(3,0,0);self.target=(self.mass,self.charge);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q310",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.mass=(x["a"],0,0);self.charge=(x["b"],0,0);self.target=target(x);self.bad=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3):self.mass,self.charge=advance((self.mass,self.charge),a)
  elif a==4:self.mass=self.mass[1:]+self.mass[:1];self.charge=self.charge[-1:]+self.charge[:-1]
  elif a==5:self.mass=self.mass[-1:]+self.mass[:-1];self.charge=self.charge[1:]+self.charge[:1]
  elif a==6:
   if (self.mass,self.charge)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
