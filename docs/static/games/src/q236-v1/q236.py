"""q236 Palimpsest Pact -- infer a convention by contrasting a visible failed offer."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,TILE,TRACE,OFFER,REPLY,FAILED,BAD=6,10,12,15,14,11,3,8
SIG=[[1,1,2],[1,2,1],[2,1,1]]
LEVELS=[{"name":n,"rule":r,"need":p} for n,r,p in [("Stored Offer",0,[1,2]),("Failed Twin",1,[1,3]),("Reciprocal Trace",2,[2,3]),("Causal Distinction",1,[1,2]),("Joint Rewrite",2,[2,3]),("Palimpsest Pact",0,[1,2])]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=ARCHIVE
  for x in (9,26,43):f[14:27,x:x+11]=TILE
  f[31:35,8:56]=TRACE;f[40:44,8:8+g.seen*7]=OFFER;f[48:52,8:8+len(g.replies)*9]=REPLY;f[55:58,43:56]=FAILED
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q236(ARCBaseGame):
 def __init__(self):self.display=D(self);self.seen=self.candidate=0;self.replies=[];self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q236",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5])
 def on_set_level(self,l):self.seen=self.candidate=0;self.replies=[];self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2,3):self.seen|=1<<(z-1);self.replies.append(SIG[x["rule"]][z-1])
  elif z==4:self.candidate=(self.candidate+1)%3
  elif z==5:
   if all(self.seen&(1<<(i-1)) for i in x["need"]) and self.candidate==x["rule"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
