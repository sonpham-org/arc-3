"""q199 Slow Consequence -- distinguish pending causes from completed effects."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHAMBER,CAUSE,PENDING,EFFECT,TARGET,TIME,BAD=12,3,9,15,10,14,6,8
LEVELS=[
 {"name":"Pending Effect","delays":[1,1,1],"target":[1,2]},
 {"name":"Different Delays","delays":[3,2,1],"target":[3,2,1]},
 {"name":"Overlap Causes","delays":[3,1,2],"target":[2,1,3]},
 {"name":"Decisions While Waiting","delays":[3,2,1],"target":[1,3,2,1]},
 {"name":"Separate Cause and Effect","delays":[2,4,1],"target":[3,1,2,3,1]},
 {"name":"Slow Consequence","delays":[4,2,3],"target":[2,3,1,2,1,3]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CHAMBER
  for i,(a,t) in enumerate(g.pending[:6]):x=8+i*8;f[15:27,x:x+6]=PENDING;f[29-t*3:31,x:x+6]=TIME
  for i,a in enumerate(g.target):x=8+i*7;f[41:47,x:x+5]=EFFECT if i<len(g.completed) else TARGET
  f[50:54,8:8+min(8,len(g.pending))*6]=CAUSE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q199(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.delays=self.target=self.pending=self.completed=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q199",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.delays=list(s["delays"]);self.target=list(s["target"]);self.pending=[];self.completed=[];self.failed=False
 def tick(self):
  nxt=[]
  for a,t in self.pending:
   if t<=1:self.completed.append(a)
   else:nxt.append((a,t-1))
  self.pending=nxt
  if self.completed!=self.target[:len(self.completed)] or len(self.pending)>8:self.failed=True;self.lose()
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3):self.pending.append((z,self.delays[z-1]));self.tick()
  elif z==5:self.tick()
  elif z==6:
   if not self.pending and self.completed==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
