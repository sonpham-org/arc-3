"""q303 Loom Dye Ledger -- conserve weighted dye through braiding and unbraiding."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LOOM,RED,YELLOW,BLUE,BRAID,AUDIT,BAD=3,10,8,11,9,15,14,6
LEVELS=[
 {"name":"First Braid","stock":2,"plan":(1,)},{"name":"Unwoven Pair","stock":2,"plan":(1,4,2)},
 {"name":"Triple Dye","stock":3,"plan":(2,2,3)},{"name":"Braid Stack","stock":3,"plan":(1,2,3,4,1)},
 {"name":"Weighted Cloth","stock":4,"plan":(3,1,2,4,4,2)},{"name":"Loom Dye Ledger","stock":4,"plan":(1,2,3,1,4,2,3)}]
def advance(state,a):
 dye,braids,stack=state;d=list(dye);b=list(braids);s=list(stack);pairs=((0,1),(1,2),(2,0))
 if a in (1,2,3):
  i,j=pairs[a-1]
  if d[i] and d[j]:d[i]-=1;d[j]-=1;b[a-1]+=1;s.append(a-1)
 elif s:
  k=s.pop();i,j=pairs[k];b[k]-=1;d[i]+=1;d[j]+=1
 return tuple(d),tuple(b),tuple(s)
def simulate(stock,plan):
 s=((stock,stock,stock),(0,0,0),())
 for a in plan:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=LOOM
  for i,(v,c) in enumerate(zip(g.dye,(RED,YELLOW,BLUE))):
   x=8+i*17;f[12:36,x:x+11]=AUDIT;f[34-v*4:34,x+2:x+9]=c
  for i,v in enumerate(g.braids):f[41:46,8+i*17:8+i*17+v*5]=BRAID
  f[52:56,8:8+g.audits*12]=AUDIT
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q303(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.dye=(1,1,1);self.braids=(0,0,0);self.stack=();self.audits=0;self.target=None;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q303",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def mass(self):return sum(self.dye)+2*sum(self.braids)
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.dye=(x["stock"],)*3;self.braids=(0,0,0);self.stack=();self.audits=0;self.target=simulate(x["stock"],x["plan"]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.dye,self.braids,self.stack=advance((self.dye,self.braids,self.stack),a)
  elif a==5:
   if self.mass()==3*x["stock"]:self.audits+=1
   else:self.bad=True;self.lose()
  elif a==6:
   if (self.dye,self.braids,self.stack)==self.target and self.audits>=2:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
