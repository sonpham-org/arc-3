"""q629 Strata Sandbox -- reversible miniature quarry tests with persistent evidence."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,ORE,FAULT,SANDBOX,EVIDENCE,CANDIDATE,BAD=9,11,13,14,15,10,6,8
LEVELS=[{"name":n,"policy":p} for n,p in [("Two Miniatures",0),("Fault Test",1),("Persistent Ore",2),("Undo Progress",1),("Irreversible Main",0),("Strata Sandbox",2)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=QUARRY;f[13:27,8:23]=SANDBOX;f[13:27,41:56]=SANDBOX;f[31:36,8:56]=FAULT;f[41:45,8:8+g.tested*12]=EVIDENCE;f[50:55,8+g.candidate*16:20+g.candidate*16]=CANDIDATE
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q629(ARCBaseGame):
 def __init__(self):self.display=D(self);self.tested=self.physical=self.candidate=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q629",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5])
 def on_set_level(self,l):self.tested=self.physical=self.candidate=0;self.bad=False
 def step(self):
  z=self.action.id.value;p=LEVELS[self.level_index]["policy"]
  if z==0:self.complete_action();return
  if z in (1,2) and not self.physical:self.physical=1;self.tested|=1<<(z-1)
  elif z==3 and self.physical:self.physical=0
  elif z==4 and not self.physical:self.candidate=(self.candidate+1)%3
  elif z==5:
   if not self.physical and self.tested==3 and self.candidate==p:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
