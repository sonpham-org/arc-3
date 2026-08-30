"""q297 Canopy Ledger -- conserve seed mass through a capacity-limited store."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,SEED,SHADE,STORE,CURSOR,TARGET,BAD=7,11,13,10,14,15,6,8
LEVELS=[{"name":n,"start":s,"target":t,"cap":c} for n,s,t,c in [("Seed Transfer",[3,0,0],[0,3,0],1),("Shade Store",[1,3,0],[2,0,2],2),("Narrow Capacity",[0,2,3],[3,1,1],1),("Global Ledger",[4,0,2],[1,3,2],2),("Deadlock Order",[2,3,2],[5,1,1],1),("Canopy Ledger",[0,4,4],[3,2,3],2)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=ORCHARD
  for i,v in enumerate(g.v):x=8+i*18;f[15:45,x:x+12]=SHADE;f[45-v*4:45,x:x+12]=SEED
  f[48:53,8:8+g.store*12]=STORE;f[54:58,8+g.cursor*18:20+g.cursor*18]=CURSOR
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q297(ARCBaseGame):
 def __init__(self):self.display=D(self);self.v=[];self.cursor=self.store=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q297",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,6])
 def on_set_level(self,l):self.v=list(LEVELS[self.level_index]["start"]);self.cursor=self.store=0;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index];n=(self.cursor+1)%3
  if z==0:self.complete_action();return
  if z==1 and self.v[self.cursor] and self.store<x["cap"]:self.v[self.cursor]-=1;self.store+=1
  elif z==2 and self.store:self.store-=1;self.v[n]+=1
  elif z==3 and not self.store:self.cursor=n
  elif z==6:
   if not self.store and self.v==x["target"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
