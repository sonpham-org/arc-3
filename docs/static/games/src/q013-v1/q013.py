"""q013 Signal Camp -- ground a partner's spatial signal policy from demonstrations."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CAMP,DEMO,SIGNAL,PARTNER,DONE,BAD=7,11,1,12,9,14,8
LEVELS=[
 {"name":"Point East","mapping":[2,0,3,1],"signals":[1,3]}, {"name":"Two Signs","mapping":[3,1,0,2],"signals":[2,0,3]},
 {"name":"Reversal","mapping":[1,3,2,0],"signals":[3,2,1,0]}, {"name":"Camp Route","mapping":[2,3,1,0],"signals":[0,2,3,1,2]},
 {"name":"Silent Policy","mapping":[3,0,2,1],"signals":[1,3,0,2,1,0]}, {"name":"Signal Camp","mapping":[1,2,0,3],"signals":[2,0,3,1,2,3,0]}]
DIRS=((0,-1),(1,0),(0,1),(-1,0))
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def mark(self,f,x,y,d,c):
  dx,dy=DIRS[d];f[y-2:y+3,x-2:x+3]=c;f[y+dy*4-1:y+dy*4+2,x+dx*4-1:x+dx*4+2]=c
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[5:58,4:60]=CAMP
  for i,out in enumerate(g.mapping):self.mark(f,11+i*14,15,i,SIGNAL);self.mark(f,11+i*14,27,out,DEMO)
  for i,s in enumerate(g.signals):self.mark(f,9+i*7,42,s,PARTNER if i>=g.progress else DONE)
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q013(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.mapping=[];self.signals=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q013",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.mapping=list(s["mapping"]);self.signals=list(s["signals"]);self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  expected=self.mapping[self.signals[self.progress]]+1
  if a!=expected:self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.signals):self.next_level()
  self.complete_action()
