"""q453 Murmuration Lineage -- ancestry tracking with a mislead-correcting parity gate."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,AVIARY,BIRD,WAKE,TRAIL,PARITY,CURSOR,BAD=3,7,13,10,15,12,6,8
LEVELS=[{"name":n,"ops":o,"ancestor":a,"signals":s,"bad":b} for n,o,a,s,b in [("Causal Flock",[1,2],0,[1,0,1],1),("Marker Swap",[2,1,1],1,[0,1,1],2),("Misleading Bird",[1,2,1,2],2,[1,1,0,1],0),("Wind Lineage",[2,2,1,2,1],0,[0,1,0,1],3),("Parity Trail",[1,1,2,1,2,2],2,[1,0,1,1,0],4),("Murmuration Lineage",[2,1,2,2,1,1,2],1,[1,1,0,1,0,0],2)]]
def transform(p,z):
 p=list(p)
 if z==1:p=p[1:]+p[:1]
 else:p[0],p[-1]=p[-1],p[0]
 return tuple(p)
def parity(x):return sum(v^(i==x["bad"]) for i,v in enumerate(x["signals"]))%2
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=AVIARY;f[12:17,8:56]=WAKE
  for i,v in enumerate(g.perm):x=9+i*17;f[23:34,x:x+11]=BIRD;f[36:40,x:x+3+v*3]=TRAIL
  f[45:49,8:8+g.claim*18]=PARITY;f[53:57,9+g.cursor*17:20+g.cursor*17]=CURSOR
  if g.badstate:f[61:64,22:42]=BAD
  return f
class Q453(ARCBaseGame):
 def __init__(self):self.display=D(self);self.perm=(0,1,2);self.progress=self.cursor=self.target=self.claim=0;self.badstate=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q453",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];p=(0,1,2)
  for z in x["ops"]:p=transform(p,z)
  self.target=p.index(x["ancestor"]);self.perm=(0,1,2);self.progress=self.cursor=self.claim=0;self.badstate=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2) and self.progress<len(x["ops"]) and z==x["ops"][self.progress]:self.perm=transform(self.perm,z);self.progress+=1
  elif z==3 and self.progress==len(x["ops"]):self.cursor=(self.cursor+1)%3
  elif z==4:self.claim=1-self.claim
  elif z==6:
   if self.progress==len(x["ops"]) and self.cursor==self.target and self.claim==parity(x):self.next_level()
   else:self.badstate=True;self.lose()
  else:self.badstate=True;self.lose()
  self.complete_action()
