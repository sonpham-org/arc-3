"""q307 Alchemy Ledger -- conserve unequal token weights through reversible reactions."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,A,B,C,REACTION,AUDIT,BAD=3,10,12,11,15,14,9,8
LEVELS=[
 {"name":"First Reaction","stock":4,"plan":(1,)},{"name":"Reversed Pair","stock":4,"plan":(1,4,2)},
 {"name":"Triple Weight","stock":5,"plan":(2,3,1)},{"name":"Closed Flask","stock":6,"plan":(1,2,3,4)},
 {"name":"Stoichiometric Audit","stock":7,"plan":(2,1,3,4,1)},{"name":"Alchemy Ledger","stock":8,"plan":(1,2,1,3,4,2)}]
def advance(state,a):
 x,y,z=state
 if a==1 and x>=2:x-=2;y+=1
 elif a==2 and x>=3:x-=3;z+=1
 elif a==3 and z:x+=1;y+=1;z-=1
 elif a==4 and y:x+=2;y-=1
 return x,y,z
def simulate(stock,plan):
 s=(stock,0,0)
 for a in plan:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=LAB
  for i,(v,c) in enumerate(zip(g.stock,(A,B,C))):
   x=8+i*17;f[12:39,x:x+11]=REACTION;f[37-v*3:37,x+2:x+9]=c
  f[47:51,8:8+g.mass() * 2]=AUDIT;f[53:57,8:8+g.audits*12]=AUDIT
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q307(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.stock=(1,0,0);self.audits=0;self.target=(1,0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q307",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def mass(self):return self.stock[0]+2*self.stock[1]+3*self.stock[2]
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.stock=(x["stock"],0,0);self.audits=0;self.target=simulate(x["stock"],x["plan"]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.stock=advance(self.stock,a)
  elif a==5:
   if self.mass()==x["stock"]:self.audits+=1
   else:self.bad=True;self.lose()
  elif a==6:
   if self.stock==self.target and self.audits>=2:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
