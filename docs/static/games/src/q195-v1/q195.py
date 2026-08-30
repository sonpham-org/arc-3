"""q195 Tempo Transfer -- scale a learned rhythm onto a slower mechanism."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,SOURCE,TARGET,BEAT,CAPTURE,DONE,BAD=15,0,10,12,9,6,14,8
LEVELS=[
 {"name":"Double Tempo","rhythm":[1,2],"scale":2}, {"name":"Slow Echo","rhythm":[2,1,2],"scale":2},
 {"name":"Triple Transfer","rhythm":[1,2,1],"scale":3}, {"name":"Uneven Rhythm","rhythm":[2,3,1,2],"scale":2},
 {"name":"Long Tempo","rhythm":[1,3,2,1,2],"scale":3}, {"name":"Tempo Transfer","rhythm":[2,1,3,2,1,2],"scale":3}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=STAGE
  for i,r in enumerate(g.rhythm):x=7+i*8;f[15:19,x:x+r*2]=SOURCE;f[25:29,x:x+r*g.scale*2]=TARGET;f[39:46,x:x+6]=DONE if i<g.progress else CAPTURE
  f[48:52,7:7+(g.t%16)*3]=BEAT
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q195(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rhythm=[];self.scale=self.progress=self.t=self.nextbeat=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q195",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.rhythm=list(s["rhythm"]);self.scale=s["scale"];self.progress=self.t=0;self.nextbeat=self.rhythm[0]*self.scale;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==5:self.t+=1
  elif a==6:
   if self.t==self.nextbeat:
    self.progress+=1
    if self.progress==len(self.rhythm):self.next_level()
    else:self.nextbeat+=self.rhythm[self.progress]*self.scale
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
