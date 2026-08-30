"""q306 Ice Crystal Exchange -- conserve crystal mass through fusion and cleavage."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ICE,RED,YELLOW,BLUE,FUSED,AUDIT,BAD=3,10,8,11,9,15,14,6
LEVELS=[
 {"name":"First Fusion","stock":2,"plan":(1,)},{"name":"Cleaved Pair","stock":2,"plan":(1,4,2)},
 {"name":"Triple Crystal","stock":3,"plan":(2,2,3)},{"name":"Fusion Stack","stock":3,"plan":(1,2,3,4,1)},
 {"name":"Weighted Ice","stock":4,"plan":(3,1,2,4,4,2)},{"name":"Ice Crystal Exchange","stock":4,"plan":(1,2,3,1,4,2,3)}]
def advance(state,a):
 shards,fused,stack=state;s=list(shards);f=list(fused);q=list(stack);pairs=((0,1),(1,2),(2,0))
 if a in (1,2,3):
  i,j=pairs[a-1]
  if s[i] and s[j]:s[i]-=1;s[j]-=1;f[a-1]+=1;q.append(a-1)
 elif q:
  k=q.pop();i,j=pairs[k];f[k]-=1;s[i]+=1;s[j]+=1
 return tuple(s),tuple(f),tuple(q)
def simulate(stock,plan):
 s=((stock,stock,stock),(0,0,0),())
 for a in plan:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=ICE
  for i,(v,c) in enumerate(zip(g.shards,(RED,YELLOW,BLUE))):
   x=8+i*17;f[12:36,x:x+11]=AUDIT;f[34-v*4:34,x+2:x+9]=c
  for i,v in enumerate(g.fused):f[41:46,8+i*17:8+i*17+v*5]=FUSED
  f[52:56,8:8+g.audits*12]=AUDIT
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q306(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.shards=(1,1,1);self.fused=(0,0,0);self.stack=();self.audits=0;self.target=None;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q306",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def mass(self):return sum(self.shards)+2*sum(self.fused)
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.shards=(x["stock"],)*3;self.fused=(0,0,0);self.stack=();self.audits=0;self.target=simulate(x["stock"],x["plan"]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.shards,self.fused,self.stack=advance((self.shards,self.fused,self.stack),a)
  elif a==5:
   if self.mass()==3*x["stock"]:self.audits+=1
   else:self.bad=True;self.lose()
  elif a==6:
   if (self.shards,self.fused,self.stack)==self.target and self.audits>=2:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
