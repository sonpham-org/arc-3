"""q536 Palimpsest Lesson -- conditional demonstrations separated from a failed twin."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,TILE,TRACE,DEMO,OUTPUT,FAILED,BAD=6,10,12,15,14,11,3,8
LEVELS=[{"name":n,"maps":m,"demo":d} for n,m,d in [("Trace Example",[[1,2,3,4],[2,1,4,3]],[[1,0,1],[4,0,0],[2,1,1]]),("Failed Twin",[[2,3,4,1],[4,3,2,1]],[[3,0,1],[1,1,1],[2,1,0],[4,0,1]]),("Conditional Shelf",[[3,1,4,2],[2,4,1,3]],[[2,1,1],[4,0,1],[1,0,0],[3,1,1]]),("No-op Mark",[[4,2,1,3],[3,1,2,4]],[[1,0,1],[2,1,0],[4,1,1],[3,0,1]]),("Delay Rewrite",[[2,4,3,1],[1,3,4,2]],[[4,1,1],[3,0,1],[1,1,0],[2,0,1],[1,1,1]]),("Palimpsest Lesson",[[3,4,1,2],[4,1,3,2]],[[2,0,1],[1,1,1],[4,0,0],[3,1,1],[4,0,1],[1,0,1]])]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=ARCHIVE;f[14:27,8:22]=TILE;f[14:27,42:56]=TILE;f[31:35,8:56]=TRACE;f[40:44,8:8+g.observed*7]=DEMO;f[49:53,8:8+len(g.result)*8]=OUTPUT;f[55:58,43:56]=FAILED
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q536(ARCBaseGame):
 def __init__(self):self.display=D(self);self.observed=0;self.result=[];self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q536",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.observed=0;self.result=[];self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index];valid=[d for d in x["demo"] if d[2]]
  if z==0:self.complete_action();return
  if z==5:self.observed+=self.observed<len(x["demo"])
  elif z in (1,2,3,4) and self.observed==len(x["demo"]) and len(self.result)<len(valid):self.result.append(x["maps"][valid[len(self.result)][1]][z-1])
  elif z==6:
   if self.result==[d[0] for d in valid]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
