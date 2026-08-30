"""q721 Tapestry Gradient -- conserve thread flow across a mid-solve adjacency rewrite."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LOOM,THREAD,TENSION,REWIRE,CURSOR,TARGET,BAD=14,9,12,13,15,10,6,8
LEVELS=[{"name":n,"start":s,"target":t,"at":a} for n,s,t,a in [
 ("Thread Flow",[3,0,0],[0,3,0],1),("Crossing Tension",[1,3,0],[2,0,2],2),("Rewired Field",[0,2,3],[3,1,1],2),("Capacity Phase",[4,0,2],[1,3,2],3),("New Adjacency",[2,3,2],[5,1,1],3),("Tapestry Gradient",[0,4,4],[3,2,3],4)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=LOOM
  for i,v in enumerate(g.v):x=8+i*18;f[15:47,x:x+12]=TENSION;f[47-v*4:47,x:x+12]=THREAD
  if g.moves>=LEVELS[g.level_index]["at"]:f[9:12,8:56:2]=REWIRE
  f[51:56,8+g.cursor*18:20+g.cursor*18]=CURSOR
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q721(ARCBaseGame):
 def __init__(self):self.display=D(self);self.v=[];self.cursor=self.moves=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q721",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,6])
 def on_set_level(self,l):self.v=list(LEVELS[self.level_index]["start"]);self.cursor=self.moves=0;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index];step=2 if self.moves>=x["at"] else 1;j=(self.cursor+step)%3
  if z==0:self.complete_action();return
  if z==1 and self.v[self.cursor]:self.v[self.cursor]-=1;self.v[j]+=1;self.moves+=1
  elif z==2 and self.v[j]:self.v[j]-=1;self.v[self.cursor]+=1;self.moves+=1
  elif z==3:self.cursor=(self.cursor+step)%3;self.moves+=1
  elif z==6:
   if self.v==x["target"] and self.moves>=x["at"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
