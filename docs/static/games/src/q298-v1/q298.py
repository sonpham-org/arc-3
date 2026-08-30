"""q298 Breakwater Ledger -- conserved cargo with a dormant first-transfer effect."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,SKIFF,CHANNEL,CARGO,LATENT,SUBGOAL,BAD=8,10,12,14,15,13,6,3
LEVELS=[{"name":n,"start":s,"plan":p} for n,s,p in [("Cargo Transfer",[3,0,0],[1,1,3,1]),("Tide Ledger",[1,3,0],[3,1,3,2,1]),("Dormant Wake",[0,2,3],[2,3,2,1,2]),("Two Subgoals",[4,0,2],[1,3,1,2,3,1]),("Terminal Gate",[2,3,2],[3,2,1,3,1,2,1]),("Breakwater Ledger",[0,4,4],[2,3,1,1,3,2,1,2])]]
def advance(v,c,z):
 a=list(v);n=(c+1)%3
 if z==1 and a[c]:a[c]-=1;a[n]+=1
 elif z==2 and a[n]:a[n]-=1;a[c]+=1
 elif z==3:c=n
 else:return None
 return tuple(a),c
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=HARBOR
  for i,v in enumerate(g.v):x=8+i*18;f[15:46,x:x+12]=CHANNEL;f[46-v*4:46,x:x+12]=CARGO
  if g.first:f[8:12,43:56]=LATENT
  f[52:56,8:8+g.stage*16]=SUBGOAL
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q298(ARCBaseGame):
 def __init__(self):self.display=D(self);self.v=();self.cursor=self.stage=0;self.first=None;self.target=None;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q298",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.v=tuple(x["start"]);self.cursor=self.stage=0;self.first=None;s=(self.v,0)
  for z in x["plan"]:s=advance(*s,z)
  self.target=(s[0],x["plan"][0]);self.bad=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3) and not self.stage:
   s=advance(self.v,self.cursor,z)
   if s is None:self.bad=True;self.lose()
   else:self.v,self.cursor=s;self.first=z if self.first is None else self.first
  elif z==4 and self.v==self.target[0] and self.stage<2:self.stage+=1
  elif z==6:
   if self.stage==2 and self.first==self.target[1]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
