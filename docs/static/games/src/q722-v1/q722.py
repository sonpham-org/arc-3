"""q722 Lockwater Gradient -- conserved barge flow with causal identity exchange."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CANAL,BARGE,WATER,GRADIENT,SWAP,CURSOR,BAD=2,7,13,10,15,12,6,8
LEVELS=[{"name":n,"start":s,"target":t} for n,s,t in [("Water Flow",[3,0,0],[0,3,0]),("Coupled Locks",[1,3,0],[2,0,2]),("Identity Swap",[0,2,3],[3,1,1]),("Capacity Phase",[4,0,2],[1,3,2]),("Causal Trail",[2,3,2],[5,1,1]),("Lockwater Gradient",[0,4,4],[3,2,3])]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=CANAL
  for i,v in enumerate(g.v):x=8+i*18;f[15:47,x:x+12]=WATER;f[47-v*4:47,x:x+12]=BARGE
  if g.swapped:f[8:12,42:56]=SWAP
  f[51:56,8+g.cursor*18:20+g.cursor*18]=CURSOR
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q722(ARCBaseGame):
 def __init__(self):self.display=D(self);self.v=[];self.cursor=0;self.swapped=self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q722",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,6])
 def on_set_level(self,l):self.v=list(LEVELS[self.level_index]["start"]);self.cursor=0;self.swapped=self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index];n=(self.cursor+1)%3
  if z==0:self.complete_action();return
  if z==1 and self.v[self.cursor]:self.v[self.cursor]-=1;self.v[n]+=1
  elif z==2 and self.v[n]:self.v[n]-=1;self.v[self.cursor]+=1
  elif z==3:self.cursor=n
  elif z==4:self.swapped=True
  elif z==6:
   if self.v==x["target"] and self.swapped:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
