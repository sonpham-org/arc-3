"""q635 Waystation Sandbox -- preserve evidence across reset miniature interventions."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,DESERT,SANDBOX,SUPPLY,EVIDENCE,CANDIDATE,MAIN,BAD=9,14,12,6,10,15,3,8
RESPONSES=[[0,1],[1,1],[1,0]]
LEVELS=[
 {"name":"Test Two Copies","policy":0},{"name":"Persistent Evidence","policy":1},
 {"name":"Reset Progress","policy":2},{"name":"Exclude Repetition","policy":1},
 {"name":"One Main Commitment","policy":0},{"name":"Waystation Sandbox","policy":2}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=DESERT;f[15:30,8:24]=SANDBOX;f[15:30,40:56]=SANDBOX;f[34:40,8:8+g.tested*14]=EVIDENCE;f[44:51,8+g.candidate*16:20+g.candidate*16]=CANDIDATE
  if g.progress:f[3:6,8:30]=MAIN
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q635(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.policy=self.tested=self.progress=self.candidate=0;self.evidence=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q635",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):self.policy=LEVELS[self.level_index]["policy"];self.tested=self.progress=self.candidate=0;self.evidence=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2) and self.progress==0:self.evidence.append(RESPONSES[self.policy][z-1]);self.tested|=1<<(z-1);self.progress=1
  elif z==3 and self.progress==1:self.progress=0
  elif z==4 and self.progress==0:self.candidate=(self.candidate+1)%3
  elif z==5:
   if self.tested==3 and self.progress==0 and self.candidate==self.policy:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
