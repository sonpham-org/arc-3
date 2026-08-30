"""q691 Tapestry Evidence -- weighted stopping after evidence rewires cursor adjacency."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LOOM,THREAD,TENSION,SCORE,REWIRE,CURSOR,BAD=14,9,12,13,15,10,6,8
LEVELS=[{"name":n,"samples":s,"at":a} for n,s,a in [("Weighted Thread",[[0,2],[1,1],[0,2]],2),("Crossing Evidence",[[2,1],[1,2],[1,2],[2,1]],2),("Rewired Cursor",[[2,3],[0,1],[1,1],[2,2]],2),("Safe Margin",[[0,1],[1,2],[0,3],[2,1]],3),("Remaining Pattern",[[1,1],[2,3],[1,2],[0,1],[1,3]],3),("Tapestry Evidence",[[2,2],[0,2],[1,1],[2,3],[0,1],[2,2]],3)]]
def lead(s):return max(range(3),key=lambda i:s[i])
def safe(s,r):a=sorted(s,reverse=True);return a[0]>a[1]+r
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=LOOM;f[13:18,8:56]=THREAD;f[26:31,8:56]=TENSION;f[39:43,8:8+sum(g.scores)*5]=SCORE
  if g.index>=LEVELS[g.level_index]["at"]:f[47:51,8:56:2]=REWIRE
  f[53:57,9+g.cursor*17:20+g.cursor*17]=CURSOR
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q691(ARCBaseGame):
 def __init__(self):self.display=D(self);self.scores=[0,0,0];self.index=self.cursor=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q691",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,6])
 def on_set_level(self,l):self.scores=[0,0,0];self.index=self.cursor=0;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z==1 and self.index<len(x["samples"]):c,w=x["samples"][self.index];self.scores[c]+=w;self.index+=1
  elif z==2:self.cursor=(self.cursor+(2 if self.index>=x["at"] else 1))%3
  elif z==6:
   remain=sum(w for _,w in x["samples"][self.index:])
   if safe(self.scores,remain) and self.cursor==lead(self.scores):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
