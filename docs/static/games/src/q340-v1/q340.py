"""q340 Vault Survey -- union bounded echo slices while tracking two conserved quantities."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,ECHO,SAMPLE,KNOWN,MASS,CHARGE,BAD=4,13,11,15,14,12,10,8
MASKS=(0b001101011,0b110010101,0b101110000)
LEVELS=[
 {"name":"First Echo","plan":(1,),"route":0},{"name":"Shared Vessel","plan":(2,1),"route":1},
 {"name":"Dual Ledger","plan":(3,2,1),"route":2},{"name":"Bounded Vault","plan":(1,3,2,1),"route":1},
 {"name":"Pressure Union","plan":(2,1,3,2,1),"route":2},{"name":"Vault Survey","plan":(3,1,2,3,1,2),"route":0}]
def simulate(plan):
 known=0;mass=6;charge=0
 for a in plan:known|=MASKS[(a-1+charge)%3];mass-=1;charge+=1
 return known,mass,charge
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=VAULT
  for i in range(3):f[10:24,9+i*17:20+i*17]=ECHO
  for i in range(9):
   x=8+(i%3)*17;y=29+(i//3)*6;f[y:y+4,x:x+9]=KNOWN if g.known&(1<<i) else SAMPLE
  f[49:53,8:8+g.mass*7]=MASS;f[54:58,8:8+g.charge*6]=CHARGE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q340(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.known=self.charge=self.route=0;self.mass=6;self.history=[];self.target=(0,6,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q340",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.known=self.charge=self.route=0;self.mass=6;self.history=[];self.target=simulate(LEVELS[self.level_index]["plan"]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):
   if self.mass:self.known|=MASKS[(a-1+self.charge)%3];self.mass-=1;self.charge+=1;self.history.append(a)
   else:self.bad=True;self.lose()
  elif a==4:self.route=(self.route+1)%3
  elif a==5:self.charge=(self.charge+1)%6
  elif a==6:
   if tuple(self.history)==x["plan"] and (self.known,self.mass,self.charge)==self.target and self.route==x["route"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
