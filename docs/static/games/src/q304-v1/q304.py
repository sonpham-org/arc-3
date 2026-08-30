"""q304 Glass Bead Exchange -- conserve bead mass through fusing and splitting."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STUDIO,RED,YELLOW,BLUE,FUSED,AUDIT,BAD=3,10,8,11,9,15,14,6
LEVELS=[
 {"name":"First Fuse","stock":2,"plan":(1,)},{"name":"Split Pair","stock":2,"plan":(1,4,2)},
 {"name":"Triple Glass","stock":3,"plan":(2,2,3)},{"name":"Fuse Stack","stock":3,"plan":(1,2,3,4,1)},
 {"name":"Weighted Beads","stock":4,"plan":(3,1,2,4,4,2)},{"name":"Glass Bead Exchange","stock":4,"plan":(1,2,3,1,4,2,3)}]
def advance(state,a):
 beads,fused,stack=state;b=list(beads);f=list(fused);s=list(stack);pairs=((0,1),(1,2),(2,0))
 if a in (1,2,3):
  i,j=pairs[a-1]
  if b[i] and b[j]:b[i]-=1;b[j]-=1;f[a-1]+=1;s.append(a-1)
 elif s:
  k=s.pop();i,j=pairs[k];f[k]-=1;b[i]+=1;b[j]+=1
 return tuple(b),tuple(f),tuple(s)
def simulate(stock,plan):
 s=((stock,stock,stock),(0,0,0),())
 for a in plan:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=STUDIO
  for i,(v,c) in enumerate(zip(g.beads,(RED,YELLOW,BLUE))):
   x=8+i*17;f[12:36,x:x+11]=AUDIT;f[34-v*4:34,x+2:x+9]=c
  for i,v in enumerate(g.fused):f[41:46,8+i*17:8+i*17+v*5]=FUSED
  f[52:56,8:8+g.audits*12]=AUDIT
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q304(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.beads=(1,1,1);self.fused=(0,0,0);self.stack=();self.audits=0;self.target=None;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q304",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def mass(self):return sum(self.beads)+2*sum(self.fused)
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.beads=(x["stock"],)*3;self.fused=(0,0,0);self.stack=();self.audits=0;self.target=simulate(x["stock"],x["plan"]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.beads,self.fused,self.stack=advance((self.beads,self.fused,self.stack),a)
  elif a==5:
   if self.mass()==3*x["stock"]:self.audits+=1
   else:self.bad=True;self.lose()
  elif a==6:
   if (self.beads,self.fused,self.stack)==self.target and self.audits>=2:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
