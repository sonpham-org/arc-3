"""q220 Vault Veil -- freeze one chamber while hidden dual resources circulate."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,CHAMBER,MASS,CHARGE,FOCUS,SEAL,GOAL,BAD=2,4,13,11,10,15,12,14,8
LEVELS=[
 {"name":"Frozen Echo","plan":(1,4)},
 {"name":"Hidden Exchange","plan":(2,1,4)},
 {"name":"Pressure Seal","plan":(3,5,4,1)},
 {"name":"Dual Circulation","plan":(1,5,2,4,3)},
 {"name":"Coupled Chambers","plan":(2,4,3,5,1,4)},
 {"name":"Vault Veil","plan":(3,5,1,4,2,5,3,4)}]
def advance(s,a):
 mass,charge,focus,seals,exposed=s;mass=list(mass);charge=list(charge)
 if a in (1,2,3):
  focus=a-1;exposed=True;hidden=[i for i in range(3) if i!=focus]
  mass[hidden[0]],mass[hidden[1]]=mass[hidden[1]],mass[hidden[0]]
  charge[hidden[0]],charge[hidden[1]]=charge[hidden[1]],charge[hidden[0]]
 elif a==4:
  j=(focus+1)%3
  if not seals&(1<<focus):mass[focus],mass[j]=mass[j],mass[focus]
  charge[focus],charge[j]=charge[j],charge[focus];exposed=False
 elif a==5:
  seals^=1<<focus;j=(focus+2)%3
  if mass[focus]:mass[focus]-=1;mass[j]+=1
  if charge[j]:charge[j]-=1;charge[focus]+=1
 return tuple(mass),tuple(charge),focus,seals,exposed
def target(x):
 s=((3,2,1),(1,2,3),0,0,False)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VAULT
  for i in range(3):
   x=8+i*18;f[10:43,x:x+14]=CHAMBER;f[46:49,x:x+g.mass[i]*3]=MASS;f[51:54,x:x+g.charge[i]*3]=CHARGE
   if i==g.focus:f[7:10,x:x+14]=FOCUS
   if g.seals&(1<<i):f[38:43,x+3:x+11]=SEAL
  f[56:59,8:8+(sum(g.mass)+sum(g.charge))*2]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q220(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self.target=target(LEVELS[0]);self._reset()
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q220",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.mass=(3,2,1);self.charge=(1,2,3);self.focus=0;self.seals=0;self.exposed=False
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.mass,self.charge,self.focus,self.seals,self.exposed=advance((self.mass,self.charge,self.focus,self.seals,self.exposed),a)
  elif a==6:
   if (self.mass,self.charge,self.focus,self.seals,self.exposed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
