"""q235 Alloy Pact -- infer a hidden convention through rotating force lanes."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,BILLET,FORCE,OFFER,REPLY,FRAME,BAD=1,7,12,14,15,10,6,8
SIG=[[0,1],[1,1],[1,0]]
LEVELS=[{"name":n,"rule":r} for n,r in [("Fair Billet",0),("Recent Force",1),("Reciprocal Lane",2),("Moving Relation",1),("Joint Cast",2),("Alloy Pact",0)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=FOUNDRY
  for x in (9,26,43):f[14:28,x:x+11]=BILLET
  f[32:37,8:56]=FORCE;f[41:45,8:8+g.seen*10]=OFFER;f[48:52,8:8+len(g.replies)*11]=REPLY;f[54:57,8:8+g.rotation*14]=FRAME
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q235(ARCBaseGame):
 def __init__(self):self.display=D(self);self.seen=self.candidate=self.rotation=0;self.replies=[];self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q235",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,5])
 def on_set_level(self,l):self.seen=self.candidate=self.rotation=0;self.replies=[];self.bad=False
 def step(self):
  z=self.action.id.value;r=LEVELS[self.level_index]["rule"]
  if z==0:self.complete_action();return
  if z in (1,2):self.replies.append(SIG[r][(z-1+self.rotation)%2]);self.seen|=1<<(z-1);self.rotation=1-self.rotation
  elif z==3:self.candidate=(self.candidate+1)%3;self.rotation=1-self.rotation
  elif z==5:
   if self.seen==3 and self.candidate==r:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
