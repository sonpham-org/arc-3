"""q060 Clockwork Tool -- assemble cams and delays into an autonomous temporal program."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WORKSHOP,CAM0,CAM1,CAM2,DELAY,OUTPUT,CURSOR,BAD=9,1,10,12,14,3,15,11,8
LEVELS=[
 {"name":"One Cam","program":[0,1]}, {"name":"Delayed Strike","program":[0,2,1]},
 {"name":"Cam Sequence","program":[1,0,3,2]}, {"name":"Autonomous Cycle","program":[2,0,1,3,2]},
 {"name":"Leave It Running","program":[0,3,1,2,3,0]}, {"name":"Clockwork Tool","program":[2,0,3,1,2,3,0]}]
def output(program):
 out=[]
 for c in program:
  if c==0:out.append(1)
  elif c==1:out.append(2)
  elif c==2:out.append(3)
  else:out.append(out[-1] if out else 1)
 return out
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=WORKSHOP
  for i,c in enumerate(g.cams):x=7+i*7;f[18:34,x:x+6]=DELAY if c<0 else [CAM0,CAM1,CAM2,DELAY][c];f[13:16,x:x+6]=CURSOR if i==g.cursor else WORKSHOP
  for i,o in enumerate(g.target):x=7+i*7;f[41:47,x:x+min(6,o+2)]=OUTPUT
  f[50:54,45:56]=OUTPUT if g.ran else WORKSHOP
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q060(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.program=self.cams=self.target=[];self.cursor=0;self.ran=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q060",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):self.program=list(LEVELS[self.level_index]["program"]);self.cams=[-1]*len(self.program);self.target=output(self.program);self.cursor=0;self.ran=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.cams[self.cursor]=(self.cams[self.cursor]+1)%4;self.ran=False
  elif z==2:self.cams[self.cursor]=(self.cams[self.cursor]-1)%4;self.ran=False
  elif z==3:self.cursor=(self.cursor-1)%len(self.cams)
  elif z==4:self.cursor=(self.cursor+1)%len(self.cams)
  elif z==5:self.ran=-1 not in self.cams and output(self.cams)==self.target
  elif z==6:
   if self.ran and self.cams==self.program:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
