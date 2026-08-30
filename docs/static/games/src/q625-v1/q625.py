"""q625 Alloy Sandbox -- persistent miniature evidence under a moving reference frame."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,SANDBOX,BILLET,FRAME,EVIDENCE,CANDIDATE,BAD=1,7,9,12,15,10,14,8
RESPONSES=[[0,1],[1,1],[1,0]]
LEVELS=[
 {"name":"Two Miniatures","policy":0},{"name":"Moving Frame","policy":1},{"name":"Persistent Evidence","policy":2},
 {"name":"Reset Simulation","policy":1},{"name":"Global Relation","policy":0},{"name":"Alloy Sandbox","policy":2}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=FOUNDRY;f[15:30,8:24]=SANDBOX;f[15:30,40:56]=SANDBOX;f[34:39,8:8+g.rotation*10]=FRAME;f[42:47,8:8+g.tested*13]=EVIDENCE;f[49:53,8+g.candidate*16:20+g.candidate*16]=CANDIDATE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q625(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.policy=self.tested=self.progress=self.rotation=self.candidate=0;self.evidence=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q625",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):self.policy=LEVELS[self.level_index]["policy"];self.tested=self.progress=self.rotation=self.candidate=0;self.evidence=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2) and self.progress==0:self.evidence.append(RESPONSES[self.policy][(z-1+self.rotation)%2]);self.tested|=1<<(z-1);self.progress=1
  elif z==3 and self.progress==1:self.progress=0;self.rotation=(self.rotation+1)%2
  elif z==4 and self.progress==0:self.candidate=(self.candidate+1)%3
  elif z==5:
   if self.tested==3 and self.progress==0 and self.candidate==self.policy:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
