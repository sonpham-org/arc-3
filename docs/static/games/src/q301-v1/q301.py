"""q301 Color Foundry -- conserve pigment mass through mixing and splitting."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,RED,YELLOW,BLUE,COMPOUND,AUDIT,BAD=3,10,8,11,9,15,14,6
LEVELS=[
 {"name":"First Blend","stock":2,"plan":(1,)},
 {"name":"Split Orange","stock":2,"plan":(1,4,2)},
 {"name":"Green Reserve","stock":3,"plan":(2,2,3)},
 {"name":"Compound Queue","stock":3,"plan":(1,2,3,4,1)},
 {"name":"Weighted Ledger","stock":4,"plan":(3,1,2,4,4,2)},
 {"name":"Color Foundry","stock":4,"plan":(1,2,3,1,4,2,3)}]
def advance(state,a):
 prim,comp,stack=state;p=list(prim);c=list(comp);s=list(stack)
 pairs=((0,1),(1,2),(2,0))
 if a in (1,2,3):
  i,j=pairs[a-1]
  if p[i] and p[j]:p[i]-=1;p[j]-=1;c[a-1]+=1;s.append(a-1)
 else:
  if s:
   k=s.pop();i,j=pairs[k];c[k]-=1;p[i]+=1;p[j]+=1
 return tuple(p),tuple(c),tuple(s)
def simulate(stock,plan):
 s=((stock,stock,stock),(0,0,0),())
 for a in plan:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=FOUNDRY
  for i,(v,color) in enumerate(zip(g.prim,(RED,YELLOW,BLUE))):
   x=8+i*17;f[12:36,x:x+11]=AUDIT;f[34-v*4:34,x+2:x+9]=color
  for i,v in enumerate(g.comp):f[40:45,8+i*17:8+i*17+v*5]=COMPOUND
  f[51:55,8:8+g.audits*12]=AUDIT
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q301(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.prim=(1,1,1);self.comp=(0,0,0);self.stack=();self.audits=0;self.target=None;self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q301",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def mass(self):return sum(self.prim)+2*sum(self.comp)
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.prim=(x["stock"],)*3;self.comp=(0,0,0);self.stack=();self.audits=0;self.target=simulate(x["stock"],x["plan"]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.prim,self.comp,self.stack=advance((self.prim,self.comp,self.stack),a)
  elif a==5:
   if self.mass()==3*x["stock"]:self.audits+=1
   else:self.bad=True;self.lose()
  elif a==6:
   if (self.prim,self.comp,self.stack)==self.target and self.audits>=2:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
