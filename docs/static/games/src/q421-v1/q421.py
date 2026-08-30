"""q421 Tapestry Revision -- recalibrate a worn rule after adjacency rewrites."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LOOM,THREAD,TENSION,WEAR,REWIRE,KNOWLEDGE,BAD=14,9,12,13,15,10,6,8
LEVELS=[{"name":n,"rule":r,"boundary":b,"spot":s} for n,r,b,s in [("Wear Thread",0,1,2),("Inverted Weave",1,2,1),("Rotated Crossing",2,3,0),("Rewired Field",1,4,2),("Sparse Calibration",2,5,1),("Tapestry Revision",0,6,0)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=LOOM;f[14:19,8:56]=THREAD;f[26:31,8:56]=TENSION;f[38:42,8:8+g.wear*7]=WEAR;f[46:50,8:56:2]=REWIRE if g.wear>=LEVELS[g.level_index]["boundary"] else THREAD;f[53:57,8+g.cursor*17:19+g.cursor*17]=KNOWLEDGE
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q421(ARCBaseGame):
 def __init__(self):self.display=D(self);self.wear=self.cursor=self.candidate=0;self.evidence=None;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q421",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,6])
 def on_set_level(self,l):self.wear=self.cursor=self.candidate=0;self.evidence=None;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z==1 and self.wear<x["boundary"]:self.wear+=1;self.cursor=(self.cursor+1)%3
  elif z==4 and self.wear==x["boundary"]:self.cursor=(self.cursor+2)%3
  elif z==2 and self.wear==x["boundary"] and self.cursor==x["spot"]:self.evidence=x["rule"]
  elif z==3 and self.evidence is not None:self.candidate=(self.candidate+1)%3
  elif z==6:
   if self.evidence==x["rule"] and self.candidate==x["rule"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
