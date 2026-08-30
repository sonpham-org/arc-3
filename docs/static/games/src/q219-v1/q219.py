"""q219 Reedbed Veil -- schedule attention while causeways alter local salinity flow."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,REED,BEETLE,FOCUS,CAUSEWAY,GOAL,BAD=10,9,14,13,11,12,0,8
LEVELS=[
 {"name":"Exposed Pool","plan":(1,4)},
 {"name":"Released Salinity","plan":(2,4,1)},
 {"name":"First Causeway","plan":(1,5,3,4)},
 {"name":"Coupled Reedbeds","plan":(2,5,1,4,3)},
 {"name":"Obstructed Channel","plan":(3,5,2,4,1,5)},
 {"name":"Reedbed Veil","plan":(1,5,3,4,2,5,1,4)}]
def advance(s,a):
 salts,focus,links,exposed=s;salts=list(salts)
 if a in (1,2,3):
  focus=a-1;exposed=True
  for i in range(3):
   if i!=focus:
    coupled=1 if links&(1<<min(i,focus)) else 0
    salts[i]=(salts[i]+i+1+coupled)%4
 elif a==4:
  left=salts[(focus-1)%3] if links&(1<<((focus-1)%3)) else 0
  salts[focus]=(salts[focus]+left+2)%4;exposed=False
 elif a==5:
  links^=1<<focus;salts[focus]=(salts[focus]+2)%4
 return tuple(salts),focus,links,exposed
def target(x):
 s=((0,1,2),0,0,False)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=WATER
  for i,v in enumerate(g.salts):
   x=8+i*18;f[10:51,x:x+14]=REED;f[15+v*7:20+v*7,x+4:x+10]=BEETLE
   if i==g.focus:f[7:10,x:x+14]=FOCUS
   if g.links&(1<<i):f[52:56,x:x+18]=CAUSEWAY
  f[58:61,8:8+sum(g.salts)*4]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q219(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.salts=(0,1,2);self.focus=0;self.links=0;self.exposed=False;self.bad=False;self.target=target(LEVELS[0])
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q219",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.salts=(0,1,2);self.focus=0;self.links=0;self.exposed=False;self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.salts,self.focus,self.links,self.exposed=advance((self.salts,self.focus,self.links,self.exposed),a)
  elif a==6:
   if (self.salts,self.focus,self.links,self.exposed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
