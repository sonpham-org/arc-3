"""q452 Lockwater Lineage -- preserve barge ancestry through visible carrier swaps."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CANAL,BARGE,WATER,TRAIL,SWAP,CURSOR,BAD=2,7,13,10,15,12,6,8
LEVELS=[{"name":n,"ops":o,"ancestor":a} for n,o,a in [("Causal Wake",[1,2],0),("Carrier Swap",[2,1,1],1),("Split Canal",[1,2,1,2],2),("Coupled Water",[2,2,1,2,1],0),("Persistent Barge",[1,1,2,1,2,2],2),("Lockwater Lineage",[2,1,2,2,1,1,2],1)]]
def transform(p,z):
 p=list(p)
 if z==1:p=p[1:]+p[:1]
 else:p[0],p[-1]=p[-1],p[0]
 return tuple(p)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=CANAL;f[12:17,8:56]=WATER
  for i,v in enumerate(g.perm):x=9+i*17;f[22:34,x:x+11]=BARGE;f[36:40,x:x+3+v*3]=TRAIL
  f[45:49,8:8+g.progress*6]=SWAP;f[53:57,9+g.cursor*17:20+g.cursor*17]=CURSOR
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q452(ARCBaseGame):
 def __init__(self):self.display=D(self);self.perm=(0,1,2);self.progress=self.cursor=self.target=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q452",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];p=(0,1,2)
  for z in x["ops"]:p=transform(p,z)
  self.target=p.index(x["ancestor"]);self.perm=(0,1,2);self.progress=self.cursor=0;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2) and self.progress<len(x["ops"]) and z==x["ops"][self.progress]:self.perm=transform(self.perm,z);self.progress+=1
  elif z==3 and self.progress==len(x["ops"]):self.cursor=(self.cursor+1)%3
  elif z==6:
   if self.progress==len(x["ops"]) and self.cursor==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
