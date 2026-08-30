"""q250 Vault Pact -- infer offer conventions while conserving mass and charge."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STONE,ARCH,CARRIER,MASS,CHARGE,MOOD,OPEN,BAD=13,3,4,12,11,10,7,14,8
LEVELS=[
 {"name":"Fair Echo","plan":(1,4)},
 {"name":"Recent Offer","plan":(2,1,5,4)},
 {"name":"Reciprocal Carrier","plan":(3,2,4,1)},
 {"name":"Dual Conservation","plan":(1,5,2,4,3)},
 {"name":"Branching Convention","plan":(2,4,1,5,3,4)},
 {"name":"Vault Pact","plan":(3,1,5,2,4,1,3,4)}]
def advance(s,a):
 mood,mass,charge,carrier,last,opened=s;mood=list(mood);mass=list(mass);charge=list(charge)
 if a in (1,2,3):
  agent=a-1;src=carrier;dst=agent
  if mass[src]:mass[src]-=1;mass[dst]+=1
  csrc=(carrier+1)%3
  if charge[csrc]:charge[csrc]-=1;charge[(agent+2)%3]+=1
  mood[agent]=(mood[agent]+agent+last+1)%3;last=agent
 elif a==4:
  opened^=1<<carrier;carrier=(carrier+1+mood[carrier])%3
 elif a==5:carrier=(carrier+1)%3
 return tuple(mood),tuple(mass),tuple(charge),carrier,last,opened
def target(x):
 s=((0,1,2),(3,2,1),(1,2,3),0,0,0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,5:59]=STONE
  for i in range(3):
   x=8+i*18;f[9:44,x:x+14]=ARCH;f[18+g.mood[i]*5:23+g.mood[i]*5,x+4:x+10]=MOOD
   f[46:49,x:x+g.mass[i]*3]=MASS;f[51:54,x:x+g.charge[i]*3]=CHARGE
   if g.opened&(1<<i):f[39:44,x+3:x+11]=OPEN
  f[6:9,9+g.carrier*18:21+g.carrier*18]=CARRIER
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q250(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self.target=target(LEVELS[0]);self._reset()
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q250",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.mood=(0,1,2);self.mass=(3,2,1);self.charge=(1,2,3);self.carrier=0;self.last=0;self.opened=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.mood,self.mass,self.charge,self.carrier,self.last,self.opened=advance((self.mood,self.mass,self.charge,self.carrier,self.last,self.opened),a)
  elif a==6:
   if (self.mood,self.mass,self.charge,self.carrier,self.last,self.opened)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
