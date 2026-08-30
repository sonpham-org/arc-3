"""q461 Gallery Provenance -- track creators independently from changing frames."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GALLERY,PAINTING,FRAME,THREAD,CHECK,BAD=11,13,12,15,14,10,8
LEVELS=[
 {"name":"First Transfer","creator":0,"ops":(1,)},{"name":"Frame Wheel","creator":1,"ops":(2,3)},
 {"name":"Crossed Art","creator":2,"ops":(4,1,3)},{"name":"False Attribution","creator":3,"ops":(3,2,1,4)},
 {"name":"Provenance Route","creator":1,"ops":(2,4,3,1,2)},{"name":"Gallery Provenance","creator":2,"ops":(1,3,4,2,3,1)}]
def transform(creators,frames,a):
 o=list(creators);s=list(frames)
 if a==1:o[0],o[-1]=o[-1],o[0]
 elif a==2:o=o[1:]+o[:1];s=s[-1:]+s[:-1]
 elif a==3:s=[(x+1)%4 for x in s]
 else:o[1],o[2]=o[2],o[1];s[0],s[3]=s[3],s[0]
 return tuple(o),tuple(s)
def result(x):
 o,s=(0,1,2,3),(0,1,2,3)
 for a in x["ops"]:o,s=transform(o,s,a)
 return o.index(x["creator"]),(sum((i+1)*v for i,v in enumerate(s))+o[-1])%4
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=GALLERY
  for i,(creator,frame) in enumerate(zip(g.creators,g.frames)):
   x=7+i*14;f[14:28,x:x+10]=PAINTING;f[17:23,x+3:x+7]=FRAME if frame%2 else THREAD;f[31+creator:34+creator,x:x+10]=THREAD
  f[45:51,7+g.target_pos*14:17+g.target_pos*14]=CHECK;f[53:57,7:7+g.check*12]=FRAME
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q461(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.creators=(0,1,2,3);self.frames=(0,1,2,3);self.target_pos=self.check=0;self.target=(0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q461",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  self.creators=(0,1,2,3);self.frames=(0,1,2,3);self.target=result(LEVELS[self.level_index]);self.target_pos=self.target[0];self.check=0;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.creators,self.frames=transform(self.creators,self.frames,a)
  elif a==5:self.check=(self.check+1)%4
  elif a==6:
   if self.creators[self.target_pos]==x["creator"] and self.check==self.target[1]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
